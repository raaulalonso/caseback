import CasebackProtocol
import Foundation
import SQLite3

enum ArchiveError: LocalizedError {
  case database(String)
  case cursor, sequence, unavailable
  var errorDescription: String? {
    switch self {
    case .database(let reason): return "No se pudo guardar o leer el archivo local (\(reason))."
    case .sequence: return "La secuencia de tramas se ha interrumpido."
    case .cursor: return "El cursor del disco no coincide con el archivo guardado."
    case .unavailable: return "El archivo local no está disponible."
    }
  }
}

struct DailyFrame {
  struct Epoch { let beats: UInt8, ibi: UInt16, quality: UInt8, activity: UInt16 }
  let seq: UInt16, boot: UInt32, uptime: Int64, gap: Bool, epochs: [Epoch]
  init(_ frame: Frame) throws {
    let p = [UInt8](frame.payload)
    guard frame.msgType == MSGStreamData, p.count >= 20, p[14] == 3, p[15] == 2,
      p[16] == 1 || p[16] == 3, p[17] == 0, p[18] == 0, p[19] > 0,
      p.count == 20 + 6 * Int(p[19])
    else { throw CaptureError.packet }
    let t = p.little(6, 8)
    guard t <= UInt64(Int64.max) - UInt64(p[19]) * 30000 else { throw CaptureError.packet }
    seq = UInt16(p.little(0, 2))
    boot = UInt32(p.little(2, 4))
    uptime = Int64(t)
    gap = p[16] & 2 != 0
    epochs = (0..<Int(p[19])).map { i in
      let j = 20 + i * 6
      return Epoch(
        beats: p[j], ibi: UInt16(p.little(j + 1, 2)), quality: p[j + 3],
        activity: UInt16(p.little(j + 4, 2)))
    }
  }
}

extension Array where Element == UInt8 {
  fileprivate func little(_ start: Int, _ count: Int) -> UInt64 {
    (0..<count).reduce(0) { $0 | UInt64(self[start + $1]) << (8 * $1) }
  }
}

struct HistoryPage {
  let first: UInt32, next: UInt32, overwritten: Bool
  init(_ frame: Frame, requested: UInt32) throws {
    let p = [UInt8](frame.payload)
    guard frame.msgType == MSGHistoryQuery, p.count == 9, p[8] <= 1 else {
      throw CaptureError.packet
    }
    first = UInt32(p.little(0, 4))
    next = UInt32(p.little(4, 4))
    overwritten = p[8] == 1
    guard requested <= first, first <= next, !overwritten || first > requested else {
      throw ArchiveError.cursor
    }
  }
}

/// A query snapshots a page. Transport sequence numbers count live and replay frames together.
struct ReplayWindow {
  let end: UInt32
  private(set) var next: UInt32

  init(page: HistoryPage, limit: UInt16) {
    next = page.first
    end = page.first + min(UInt32(limit), page.next - page.first)
  }

  mutating func receive(
    _ batch: DailyFrame, after previousSeq: UInt16?, archive: PilotArchive, unit: String
  ) throws {
    guard next < end else { throw ArchiveError.cursor }
    guard previousSeq.map({ $0 &+ 1 == batch.seq }) ?? (batch.seq == 0) else {
      throw ArchiveError.sequence
    }
    try archive.accept(batch, cursor: next, unit: unit)
    next += 1
  }
}

struct ArchiveSummary {
  var device = "", epochs = 0, lost = 0, previouslyAcknowledged = 0, interruptions = 0,
    rawSamples = 0
  var activity: Int?, utcMs: Int64?, boot: UInt32?, uptime: Int64?
  var boots = 0
  var temperature: String?, battery: String?, temperatureAt: Date?, batteryAt: Date?
}
struct StoredCapture: Identifiable {
  let id: String, utc: Int64, n: Int
}
struct StoredEpoch: Identifiable {
  let id: Int64, boot: UInt32, uptime: Int64, utc: Int64?, activity: Int, gap: Bool
}

final class PilotArchive {
  private enum Param {
    case str(String)
    case int(Int64)
    case blob(Data)
  }
  private var db: OpaquePointer?
  let url: URL
  private static let transient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

  static func openDefault() throws -> PilotArchive {
    var dir = try FileManager.default.url(
      for: .applicationSupportDirectory, in: .userDomainMask,
      appropriateFor: nil, create: true
    ).appendingPathComponent("Measurements")
    try FileManager.default.createDirectory(
      at: dir, withIntermediateDirectories: true,
      attributes: [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication])
    var values = URLResourceValues()
    values.isExcludedFromBackup = true
    try dir.setResourceValues(values)
    return try PilotArchive(url: dir.appendingPathComponent("measurements.sqlite"))
  }

  init(url: URL) throws {
    self.url = url
    guard
      sqlite3_open_v2(
        url.path, &db, SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX, nil)
        == SQLITE_OK
    else {
      let error = issue()
      sqlite3_close(db)
      db = nil
      throw error
    }
    do {
      sqlite3_busy_timeout(db, 3000)
      try sql("PRAGMA journal_mode=WAL")
      try sql("PRAGMA synchronous=FULL")
      try sql(
        "CREATE TABLE IF NOT EXISTS devices (unit TEXT PRIMARY KEY, cursor INTEGER NOT NULL DEFAULT 0, seen INTEGER NOT NULL)"
      )
      try sql(
        "CREATE TABLE IF NOT EXISTS anchors (unit TEXT, boot INTEGER, ticks INTEGER, utc INTEGER NOT NULL, PRIMARY KEY(unit,boot,ticks))"
      )
      try sql(
        "CREATE TABLE IF NOT EXISTS lost (unit TEXT, start INTEGER, end INTEGER, PRIMARY KEY(unit,start))"
      )
      try sql(
        """
        CREATE TABLE IF NOT EXISTS epochs (unit TEXT, cursor INTEGER, idx INTEGER, boot INTEGER,
        ticks INTEGER, beats INTEGER, ibi INTEGER, quality INTEGER, activity INTEGER, gap INTEGER,
        PRIMARY KEY(unit,cursor,idx))
        """)
      try sql(
        """
        CREATE TABLE IF NOT EXISTS live (id INTEGER PRIMARY KEY, unit TEXT NOT NULL, session TEXT NOT NULL,
        utc INTEGER NOT NULL, gap INTEGER NOT NULL, n INTEGER NOT NULL, payload BLOB NOT NULL)
        """)
      try sql("CREATE INDEX IF NOT EXISTS live_unit_session ON live(unit,session,id)")
      try sql(
        "CREATE TABLE IF NOT EXISTS readings (unit TEXT, name TEXT, value TEXT, at INTEGER, PRIMARY KEY(unit,name))"
      )
      try sql(
        "CREATE TABLE IF NOT EXISTS captures (unit TEXT, session TEXT, utc INTEGER, first_id INTEGER, n INTEGER, PRIMARY KEY(unit,session))"
      )
      var version = 0
      try sql("PRAGMA user_version") { version = Int(sqlite3_column_int($0, 0)) }
      if version < 1 {
        try transaction {
          try sql(
            "INSERT OR IGNORE INTO captures SELECT unit,session,MIN(utc),MIN(id),SUM(n) FROM live GROUP BY unit,session"
          )
          try sql(
            """
            CREATE TRIGGER IF NOT EXISTS count_live AFTER INSERT ON live BEGIN
              INSERT INTO captures VALUES(NEW.unit,NEW.session,NEW.utc,NEW.id,NEW.n)
                ON CONFLICT(unit,session) DO UPDATE SET n=n+NEW.n;
            END
            """)
          try sql("PRAGMA user_version=1")
        }
      }
      if version < 2 {
        try transaction {
          try sql("ALTER TABLE lost ADD COLUMN overwritten INTEGER NOT NULL DEFAULT 1")
          try sql("PRAGMA user_version=2")
        }
      }
    } catch {
      sqlite3_close(db)
      db = nil
      throw error
    }
  }

  deinit { sqlite3_close(db) }

  private func issue() -> ArchiveError {
    .database(db.map { String(cString: sqlite3_errmsg($0)) } ?? "SQLite")
  }

  private func sql(
    _ stmt: String, _ args: [Param] = [], row: (OpaquePointer) throws -> Void = { _ in }
  ) throws {
    var raw: OpaquePointer?
    guard sqlite3_prepare_v2(db, stmt, -1, &raw, nil) == SQLITE_OK, let s = raw else {
      throw issue()
    }
    defer { sqlite3_finalize(s) }
    for (i, arg) in args.enumerated() {
      let pos = Int32(i + 1)
      let rc: Int32
      switch arg {
      case .str(let v): rc = sqlite3_bind_text(s, pos, v, -1, Self.transient)
      case .int(let v): rc = sqlite3_bind_int64(s, pos, v)
      case .blob(let v):
        rc = v.withUnsafeBytes {
          sqlite3_bind_blob(s, pos, $0.baseAddress, Int32(v.count), Self.transient)
        }
      }
      guard rc == SQLITE_OK else { throw issue() }
    }
    while true {
      switch sqlite3_step(s) {
      case SQLITE_ROW: try row(s)
      case SQLITE_DONE: return
      default: throw issue()
      }
    }
  }

  private func transaction(_ action: () throws -> Void) throws {
    try sql("BEGIN IMMEDIATE")
    do {
      try action()
      try sql("COMMIT")
    } catch {
      try? sql("ROLLBACK")
      throw error
    }
  }

  func saveAnchor(unit: String, boot: UInt32, ticks: Int64, utc: Int64) throws {
    try transaction {
      try sql(
        "INSERT INTO devices(unit,seen) VALUES(?,?) ON CONFLICT(unit) DO UPDATE SET seen=excluded.seen",
        [.str(unit), .int(utc)])
      try sql(
        "INSERT OR REPLACE INTO anchors VALUES(?,?,?,?)",
        [.str(unit), .int(Int64(boot)), .int(ticks), .int(utc)])
    }
  }

  func cursor(_ unit: String) throws -> UInt32 {
    var result: UInt32?
    try sql("SELECT cursor FROM devices WHERE unit=?", [.str(unit)]) {
      result = UInt32(exactly: sqlite3_column_int64($0, 0))
    }
    guard let result else { throw ArchiveError.cursor }
    return result
  }

  func acceptPage(_ page: HistoryPage, requested: UInt32, unit: String) throws {
    guard page.first != requested else { return }
    try transaction {
      guard try cursor(unit) == requested else { throw ArchiveError.cursor }
      try sql(
        "INSERT INTO lost VALUES(?,?,?,?)",
        [
          .str(unit), .int(Int64(requested)), .int(Int64(page.first)),
          .int(page.overwritten ? 1 : 0),
        ])
      try sql("UPDATE devices SET cursor=? WHERE unit=?", [.int(Int64(page.first)), .str(unit)])
    }
  }

  func accept(_ batch: DailyFrame, cursor index: UInt32, unit: String) throws {
    try transaction {
      guard index < .max, try cursor(unit) == index else { throw ArchiveError.cursor }
      for (i, e) in batch.epochs.enumerated() {
        try sql(
          "INSERT INTO epochs VALUES(?,?,?,?,?,?,?,?,?,?)",
          [
            .str(unit), .int(Int64(index)), .int(Int64(i)), .int(Int64(batch.boot)),
            .int(batch.uptime + Int64(i) * 30000),
            .int(Int64(e.beats)), .int(Int64(e.ibi)), .int(Int64(e.quality)),
            .int(Int64(e.activity)), .int(batch.gap && i == 0 ? 1 : 0),
          ])
      }
      try sql("UPDATE devices SET cursor=? WHERE unit=?", [.int(Int64(index) + 1), .str(unit)])
    }
  }

  func live(_ frame: Frame, batch: PilotBatch, unit: String, session: String, utc: Int64, gap: Bool)
    throws
  {
    try sql(
      "INSERT INTO live(unit,session,utc,gap,n,payload) VALUES(?,?,?,?,?,?)",
      [
        .str(unit), .str(session), .int(utc), .int(gap ? 1 : 0), .int(Int64(batch.values.count)),
        .blob(frame.payload),
      ])
  }

  func devices() throws -> [String] {
    var list = [String]()
    try sql("SELECT unit FROM devices ORDER BY seen DESC,unit") {
      list.append(String(cString: sqlite3_column_text($0, 0)))
    }
    return list
  }

  private func wallTime(unit: String, boot: Int64, uptime: Int64) throws -> Int64? {
    var result: Int64?
    try sql(
      "SELECT ticks,utc FROM anchors WHERE unit=? AND boot=? ORDER BY abs(ticks-?) LIMIT 1",
      [.str(unit), .int(boot), .int(uptime)]
    ) { s in
      let (value, overflow) = sqlite3_column_int64(s, 1).addingReportingOverflow(
        uptime - sqlite3_column_int64(s, 0))
      if !overflow { result = value }
    }
    return result
  }

  func summary(_ unit: String) throws -> ArchiveSummary {
    var s = ArchiveSummary()
    s.device = unit
    try sql(
      "SELECT COUNT(*),TOTAL(gap),COUNT(DISTINCT boot) FROM epochs WHERE unit=?", [.str(unit)]
    ) {
      s.epochs = Int(sqlite3_column_int64($0, 0))
      s.interruptions = Int(sqlite3_column_int64($0, 1))
      s.boots = Int(sqlite3_column_int64($0, 2))
    }
    try sql(
      "SELECT overwritten,SUM(end-start) FROM lost WHERE unit=? GROUP BY overwritten", [.str(unit)]
    ) {
      let count = Int(sqlite3_column_int64($0, 1))
      if sqlite3_column_int($0, 0) == 1 { s.lost = count } else { s.previouslyAcknowledged = count }
    }
    try sql("SELECT TOTAL(n) FROM captures WHERE unit=?", [.str(unit)]) {
      s.rawSamples = Int(sqlite3_column_int64($0, 0))
    }
    try sql(
      "SELECT boot,ticks,activity FROM epochs WHERE unit=? ORDER BY cursor DESC,idx DESC LIMIT 1",
      [.str(unit)]
    ) { row in
      let boot = sqlite3_column_int64(row, 0)
      let ticks = sqlite3_column_int64(row, 1)
      s.boot = UInt32(exactly: boot)
      s.uptime = ticks
      s.activity = Int(sqlite3_column_int64(row, 2))
      s.utcMs = try wallTime(unit: unit, boot: boot, uptime: ticks)
    }
    try sql("SELECT name,value,at FROM readings WHERE unit=?", [.str(unit)]) { row in
      let key = String(cString: sqlite3_column_text(row, 0))
      let value = String(cString: sqlite3_column_text(row, 1))
      let date = Date(timeIntervalSince1970: Double(sqlite3_column_int64(row, 2)) / 1000)
      if key == "battery" {
        s.battery = value
        s.batteryAt = date
      } else if key == "temperature" {
        s.temperature = value
        s.temperatureAt = date
      }
    }
    return s
  }

  enum Reading: String { case temperature, battery }

  func lastReading(_ reading: Reading, value: String, unit: String, at: Date = Date()) throws {
    try sql(
      "INSERT OR REPLACE INTO readings VALUES(?,?,?,?)",
      [
        .str(unit), .str(reading.rawValue), .str(value),
        .int(Int64(at.timeIntervalSince1970 * 1000)),
      ])
  }

  func recent(_ unit: String) throws -> [StoredEpoch] {
    var out = [StoredEpoch]()
    try sql(
      "SELECT rowid,boot,ticks,activity,gap FROM epochs WHERE unit=? ORDER BY cursor DESC,idx DESC LIMIT 20",
      [.str(unit)]
    ) { s in
      let boot = sqlite3_column_int64(s, 1)
      let ticks = sqlite3_column_int64(s, 2)
      guard let bootID = UInt32(exactly: boot) else { throw ArchiveError.cursor }
      out.append(
        StoredEpoch(
          id: sqlite3_column_int64(s, 0), boot: bootID, uptime: ticks,
          utc: try wallTime(unit: unit, boot: boot, uptime: ticks),
          activity: Int(sqlite3_column_int64(s, 3)), gap: sqlite3_column_int(s, 4) != 0))
    }
    return out
  }

  func captures(_ unit: String) throws -> [StoredCapture] {
    var out = [StoredCapture]()
    try sql("SELECT session,utc,n FROM captures WHERE unit=? ORDER BY first_id DESC", [.str(unit)])
    { s in
      out.append(
        StoredCapture(
          id: String(cString: sqlite3_column_text(s, 0)), utc: sqlite3_column_int64(s, 1),
          n: Int(sqlite3_column_int64(s, 2))))
    }
    return out
  }

  func export(
    unit: String, daily: Bool, session: String? = nil,
    directory: URL = FileManager.default.temporaryDirectory
  ) throws -> URL {
    let url = directory.appendingPathComponent(
      "Caseback-\(unit)-\(daily ? "actividad" : "capturas")-\(UUID().uuidString).csv")
    guard
      FileManager.default.createFile(
        atPath: url.path, contents: nil,
        attributes: [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication])
    else {
      throw ArchiveError.unavailable
    }
    do {
      let file = try FileHandle(forWritingTo: url)
      defer { try? file.close() }
      func write(_ line: String) throws { try file.write(contentsOf: Data((line + "\n").utf8)) }
      if daily {
        try write(
          "record,device_id,cursor,cursor_end_exclusive,boot_id,uptime_ms,utc_ms,gap,activity_changes,pulse_fields_present,beats,mean_ibi_ms,quality"
        )
        try sql("SELECT start,end,overwritten FROM lost WHERE unit=? ORDER BY start", [.str(unit)])
        { s in
          let reason =
            sqlite3_column_int(s, 2) == 1 ? "missing_with_overwrite" : "previously_acknowledged"
          try write(
            "\(reason),\(unit),\(sqlite3_column_int64(s,0)),\(sqlite3_column_int64(s,1)),,,,,,,,,")
        }
        try sql(
          "SELECT cursor,boot,ticks,gap,activity,beats,ibi,quality FROM epochs WHERE unit=? ORDER BY cursor,idx",
          [.str(unit)]
        ) { s in
          let v = (0..<8).map { sqlite3_column_int64(s, Int32($0)) }
          let utc = try wallTime(unit: unit, boot: v[1], uptime: v[2]).map(String.init) ?? ""
          let pulse = v[5] == 0 && v[6] == 0 && v[7] == 0 ? "0,,," : "1,\(v[5]),\(v[6]),\(v[7])"
          try write(
            "epoch,\(unit),\(v[0]),,\(v[1]),\(v[2]),\(utc),\(v[3]),\(v[4]),\(pulse)")
        }
      } else {
        try write(
          "device_id,boot_id,utc_ms,uptime_ms,seq,gap,stream,green_counts,x_counts,y_counts,z_counts,session"
        )
        let selected: String
        if let session {
          selected = session
        } else if let first = try captures(unit).first {
          selected = first.id
        } else {
          throw ArchiveError.unavailable
        }
        try sql(
          "SELECT session,utc,gap,payload FROM live WHERE unit=? AND session=? ORDER BY id",
          [.str(unit), .str(selected)]
        ) { s in
          guard let bytes = sqlite3_column_blob(s, 3) else { throw CaptureError.packet }
          let f = try PilotBatch(
            Frame(
              msgType: MSGStreamData,
              payload: Data(bytes: bytes, count: Int(sqlite3_column_bytes(s, 3)))))
          let session = String(cString: sqlite3_column_text(s, 0))
          let utc = sqlite3_column_int64(s, 1)
          let gap = sqlite3_column_int(s, 2)
          for (i, fields) in f.rows.enumerated() {
            let offset = Int64(f.offsetMs(i))
            try write(
              "\(unit),\(f.boot),\(utc+offset),\(f.uptime+UInt64(offset)),\(f.seq),\(i == 0 ? gap : 0),\(f.id),\(fields),\(session)"
            )
          }
        }
      }
      try file.synchronize()
    } catch {
      try? FileManager.default.removeItem(at: url)
      throw error
    }
    return url
  }
}
