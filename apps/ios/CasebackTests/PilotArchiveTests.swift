import CasebackProtocol
import Foundation
import SQLite3
import XCTest

@testable import Caseback

final class PilotArchiveTests: XCTestCase {
  private var directory: URL!
  override func setUpWithError() throws {
    directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
  }
  override func tearDownWithError() throws { try FileManager.default.removeItem(at: directory) }

  private var dbURL: URL { directory.appendingPathComponent("test.sqlite") }
  private func page(_ first: UInt32, _ end: UInt32, _ flag: UInt8, requested: UInt32) throws
    -> HistoryPage
  {
    let bytes =
      [first, end].flatMap { v in (0..<4).map { UInt8(truncatingIfNeeded: v >> ($0 * 8)) } } + [
        flag
      ]
    return try HistoryPage(
      Frame(msgType: MSGHistoryQuery, payload: Data(bytes)), requested: requested)
  }
  private func epoch(boot: UInt8 = 11, seq: UInt16 = .max, flags: UInt8 = 1, values: [UInt8] = [4])
    throws -> DailyFrame
  {
    let header: [UInt8] = [
      UInt8(truncatingIfNeeded: seq), UInt8(seq >> 8), boot, 0, 0, 0, 200, 0, 0, 0, 0, 0, 0, 0, 3,
      2, flags, 0, 0, UInt8(values.count),
    ]
    return try DailyFrame(
      Frame(msgType: MSGStreamData, payload: Data(header + values.flatMap { [0, 0, 0, 0, $0, 0] })))
  }
  func testCommittedCursorSurvivesReopenAndRetainsUnanchoredBoot() throws {
    var live: PilotArchive? = try PilotArchive(url: dbURL)
    try XCTUnwrap(live).saveAnchor(unit: "AA", boot: 10, ticks: 100, utc: 10000)
    let window = try page(7, 9, 1, requested: 0)
    try XCTUnwrap(live).acceptPage(window, requested: 0, unit: "AA")
    try XCTUnwrap(live).accept(epoch(boot: 10, flags: 3, values: [8, 5]), cursor: 7, unit: "AA")
    live = nil  // simulate app death before ACK or receipt of the second frame
    let file = try PilotArchive(url: dbURL)
    XCTAssertEqual(try file.cursor("AA"), 8)
    XCTAssertThrowsError(try file.accept(epoch(boot: 10), cursor: 7, unit: "AA"))
    try file.accept(epoch(), cursor: 8, unit: "AA")
    let archived = try file.recent("AA")
    XCTAssertEqual(archived.map(\.activity), [4, 5, 8])
    XCTAssertEqual(archived.map(\.utc), [nil, 40100, 10100])
    XCTAssertEqual(archived.map(\.gap), [false, false, true])
    let initial = try file.summary("AA")
    XCTAssertEqual(initial.epochs, 3)
    XCTAssertEqual(initial.lost, 7)
    XCTAssertEqual(initial.boots, 2)
    try file.saveAnchor(unit: "AA", boot: 11, ticks: 1000, utc: 60000)
    XCTAssertEqual(try file.summary("AA").utcMs, 59200)
    try file.saveAnchor(unit: "BB", boot: 11, ticks: 1000, utc: 160000)
    XCTAssertEqual(try file.cursor("BB"), 0)
    XCTAssertEqual(try file.summary("AA").utcMs, 59200)
    let savedCSV = try String(
      contentsOf: file.export(unit: "AA", daily: true, directory: directory), encoding: .utf8)
    XCTAssertTrue(savedCSV.contains("missing_with_overwrite,AA,0,7"))
    XCTAssertTrue(savedCSV.contains("epoch,AA,8,,11,200,59200,0,4,0,,,"))
  }

  func testRejectsInvalidReplayWithoutAdvancingArchive() throws {
    let file = try PilotArchive(url: dbURL)
    try file.saveAnchor(unit: "01", boot: 1, ticks: 1, utc: 1)
    XCTAssertThrowsError(try page(2, 1, 1, requested: 0))
    XCTAssertNoThrow(try page(1, 1, 0, requested: 0))
    XCTAssertThrowsError(try page(0, 1, 1, requested: 0))
    XCTAssertThrowsError(try page(0, 1, 2, requested: 0))
    XCTAssertThrowsError(try epoch(flags: 0))
    XCTAssertThrowsError(try epoch(flags: 5))
    XCTAssertThrowsError(try epoch(values: []))
    XCTAssertThrowsError(try file.accept(epoch(), cursor: 1, unit: "01"))
    XCTAssertEqual(try file.cursor("01"), 0)
    XCTAssertEqual(try file.summary("01").epochs, 0)
  }

  func testRawCaptureDurableAndSeparateAcrossReconnects() throws {
    let file = try PilotArchive(url: dbURL)
    try file.saveAnchor(unit: "77", boot: 1, ticks: 0, utc: 9000)
    let payload: [UInt8] = [
      0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0xf4, 1, 2, 13, 0, 0, 17, 0, 0,
    ]
    let frame = Frame(msgType: MSGStreamData, payload: Data(payload))
    for (i, session) in ["first", "second"].enumerated() {
      try file.live(
        frame, batch: PilotBatch(frame), unit: "77", session: session, utc: 9000 + Int64(i) * 50,
        gap: i == 1)
    }
    let reopened = try PilotArchive(url: dbURL)
    XCTAssertEqual(try reopened.summary("77").rawSamples, 4)
    XCTAssertEqual(try reopened.captures("77").map(\.id), ["second", "first"])
    let output = try reopened.export(unit: "77", daily: false, directory: directory)
    let csv = try String(contentsOf: output, encoding: .utf8)
    XCTAssertEqual(csv.split(separator: "\n").count, 3)
    XCTAssertTrue(csv.contains("77,1,9050,0,0,1,1,13,,,,second"))
    XCTAssertFalse(csv.contains("first"))
    let previous = try reopened.export(
      unit: "77", daily: false, session: "first", directory: directory)
    XCTAssertTrue(
      try String(contentsOf: previous, encoding: .utf8).contains("77,1,9020,20,0,0,1,17,,,,first"))
  }
  func testFirmwareFramesAndSharedSequenceWrap() throws {
    // Complete notifications emitted by the Zephyr firmware's C encoders, including CRC16.
    func bytes(_ hex: String) -> Data {
      Data(
        stride(from: 0, to: hex.utf8.count, by: 2).map {
          let i = hex.index(hex.startIndex, offsetBy: $0)
          return UInt8(hex[i..<hex.index(i, offsetBy: 2)], radix: 16)!
        })
    }
    let received = try HistoryPage(
      decodeFrame(bytes("a50112090006000000c021000000cbc3")), requested: 6)
    let frame = try DailyFrame(
      decodeFrame(bytes("a501101a0000001300000020bf0200000000000302010000010000000006005dd0")))
    XCTAssertEqual(received.first, 6)
    XCTAssertEqual(received.next, 8640)
    XCTAssertEqual(frame.boot, 19)
    XCTAssertEqual(frame.uptime, 180000)
    XCTAssertEqual(frame.epochs[0].activity, 6)
    let file = try PilotArchive(url: dbURL)
    try file.saveAnchor(unit: "AC", boot: 19, ticks: 180000, utc: 1_800_000)
    try file.acceptPage(page(6, 8640, 1, requested: 0), requested: 0, unit: "AC")
    var transfer = ReplayWindow(page: received, limit: 16)
    XCTAssertEqual(transfer.end, 22)
    try transfer.receive(frame, after: 0xffff, archive: file, unit: "AC")
    XCTAssertThrowsError(try transfer.receive(epoch(seq: 3), after: 0, archive: file, unit: "AC"))
    XCTAssertEqual(transfer.next, 7)
    XCTAssertEqual(try file.cursor("AC"), 7)
    // A new connection starts its own seq counter. Flash cursors continue.
    var resumed = try ReplayWindow(page: page(7, 8640, 0, requested: 7), limit: 16)
    try resumed.receive(epoch(seq: 0), after: nil, archive: file, unit: "AC")
    XCTAssertEqual(try file.cursor("AC"), 8)
  }

  func testSQLiteWriteFailureRollsBackWholeFrameAndPreservesCursor() throws {
    let file = try PilotArchive(url: dbURL)
    try file.saveAnchor(unit: "03", boot: 1, ticks: 1, utc: 1)
    var db: OpaquePointer?
    XCTAssertEqual(sqlite3_open(dbURL.path, &db), SQLITE_OK)
    defer { sqlite3_close(db) }
    XCTAssertEqual(
      sqlite3_exec(
        db,
        "CREATE TRIGGER fail_second BEFORE INSERT ON epochs WHEN NEW.idx=1 BEGIN SELECT RAISE(ABORT,'test failure'); END;",
        nil, nil, nil), SQLITE_OK)
    var replay = try ReplayWindow(page: page(0, 1, 0, requested: 0), limit: 16)
    XCTAssertThrowsError(
      try replay.receive(epoch(seq: 0, values: [1, 2]), after: nil, archive: file, unit: "03"))
    XCTAssertEqual(replay.next, 0)
    XCTAssertEqual(try file.cursor("03"), 0)
    XCTAssertEqual(try file.summary("03").epochs, 0)
    XCTAssertEqual(sqlite3_exec(db, "DROP TRIGGER fail_second", nil, nil, nil), SQLITE_OK)
    try replay.receive(epoch(seq: 0, values: [1, 2]), after: nil, archive: file, unit: "03")
    XCTAssertEqual(replay.next, 1)
    XCTAssertEqual(try file.summary("03").epochs, 2)
    try file.lastReading(
      .temperature, value: "28.13 °C", unit: "03", at: Date(timeIntervalSince1970: 42))
    let reopened = try PilotArchive(url: dbURL)
    XCTAssertEqual(try reopened.summary("03").temperature, "28.13 °C")
    XCTAssertEqual(try reopened.summary("03").temperatureAt, Date(timeIntervalSince1970: 42))
  }

  func testThreeDaysInSixteenFramePagesAfterReconnect() throws {
    let count = 3 * 24 * 120
    let unit = "0800"
    var archive = try PilotArchive(url: dbURL)
    try archive.saveAnchor(unit: unit, boot: 1, ticks: 0, utc: 1000)
    var previousSeq: UInt16?
    var index = 0
    while index < count {
      let reply = try page(UInt32(index), UInt32(count), 0, requested: UInt32(index))
      var window = ReplayWindow(page: reply, limit: 16)
      while window.next < window.end {
        let sequence: UInt16 = previousSeq.map { $0 &+ 1 } ?? 0
        let header: [UInt8] = [
          UInt8(truncatingIfNeeded: sequence), UInt8(sequence >> 8), 1, 0, 0, 0,
        ]
        let ticks = UInt64(index) * 30000
        let clock: [UInt8] = (0..<8).map { UInt8(truncatingIfNeeded: ticks >> ($0 * 8)) }
        let data: [UInt8] = [3, 2, 1, 0, 0, 1, 0, 0, 0, 0, UInt8(index % 31), 0]
        let b = try DailyFrame(Frame(msgType: MSGStreamData, payload: Data(header + clock + data)))
        try window.receive(b, after: previousSeq, archive: archive, unit: unit)
        index += 1
        previousSeq = sequence
        if index == 4327 {  // new connection between two frames of a page
          archive = try PilotArchive(url: dbURL)
          XCTAssertEqual(try archive.cursor(unit), UInt32(index))
          previousSeq = nil
          break
        }
      }
    }
    let summary = try archive.summary(unit)
    XCTAssertEqual(summary.epochs, 8640)
    XCTAssertEqual(summary.utcMs, Int64(count - 1) * 30000 + 1000)
    XCTAssertEqual(try archive.cursor(unit), 8640)
  }

  func testFreshPhoneUnderstandsHistoryAlreadyAcknowledgedByPastInstall() throws {
    let file = try PilotArchive(url: dbURL)
    try file.saveAnchor(unit: "AA", boot: 1, ticks: 0, utc: 1000)
    try file.acceptPage(page(15, 15, 0, requested: 0), requested: 0, unit: "AA")
    XCTAssertEqual(try file.cursor("AA"), 15)
    XCTAssertEqual(try file.summary("AA").previouslyAcknowledged, 15)
    XCTAssertEqual(try file.summary("AA").lost, 0)
    let csv = try String(
      contentsOf: file.export(unit: "AA", daily: true, directory: directory), encoding: .utf8)
    XCTAssertTrue(csv.contains("previously_acknowledged,AA,0,15,"))
    XCTAssertTrue(
      csv.split(separator: "\n").allSatisfy {
        $0.split(separator: ",", omittingEmptySubsequences: false).count == 13
      })
  }

}
