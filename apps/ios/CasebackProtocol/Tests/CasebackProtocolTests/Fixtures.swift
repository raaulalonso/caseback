import Foundation
import XCTest
@testable import CasebackProtocol

enum Fixtures {
    static func url(named file: String) throws -> URL {
        let name = (file as NSString).deletingPathExtension
        let ext = (file as NSString).pathExtension
        return try XCTUnwrap(
            Bundle.module.url(forResource: name, withExtension: ext, subdirectory: "Fixtures/golden"),
            "missing fixture \(file)"
        )
    }

    static func data(named name: String) throws -> Data {
        try Data(contentsOf: url(named: "\(name).bin"))
    }

    struct Entry {
        let file: String
        /// "ok" or an error name from the manifest
        let status: String
        let msgType: UInt8?
        let payloadLen: Int?
    }

    static func manifest() throws -> [Entry] {
        let text = try String(contentsOf: url(named: "manifest.txt"), encoding: .utf8)
        return text.split(separator: "\n").compactMap { line in
            guard !line.hasPrefix("#") else { return nil }
            let f = line.split(separator: " ").map(String.init)
            guard f.count >= 2 else { return nil }
            if f[1] == "ok", f.count == 4 {
                let type = UInt8(f[2].dropFirst(2), radix: 16)
                return Entry(file: f[0], status: "ok", msgType: type, payloadLen: Int(f[3]))
            }
            return Entry(file: f[0], status: f[1], msgType: nil, payloadLen: nil)
        }
    }

    static func errorName(_ code: ErrorCode) -> String {
        switch code {
        case .truncated: return "truncated"
        case .badMagic: return "bad_magic"
        case .unsupportedVersion: return "unsupported_version"
        case .payloadTooLong: return "payload_too_long"
        case .lengthMismatch: return "length_mismatch"
        case .badCRC: return "bad_crc"
        default: return "other(\(code))"
        }
    }
}
