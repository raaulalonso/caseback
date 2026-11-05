import XCTest
@testable import CasebackProtocol

final class CRC16Tests: XCTestCase {
    func testEmpty() {
        XCTAssertEqual(CRC16.ccittFalse(Data()), 0xFFFF)
    }

    func testCheckValue123456789() {
        XCTAssertEqual(CRC16.ccittFalse(Data("123456789".utf8)), 0x29B1)
    }

    func testSingleZeroByte() {
        XCTAssertEqual(CRC16.ccittFalse(Data([0x00])), 0xE1F0)
    }
}
