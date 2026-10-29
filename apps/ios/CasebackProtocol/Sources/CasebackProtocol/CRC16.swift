import Foundation

public enum CRC16 {
    /// CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflect, no xorout).
    public static func ccittFalse(_ data: Data) -> UInt16 {
        var crc: UInt16 = 0xFFFF
        for byte in data {
            crc ^= UInt16(byte) << 8
            for _ in 0..<8 {
                if crc & 0x8000 != 0 {
                    crc = (crc << 1) ^ 0x1021
                } else {
                    crc <<= 1
                }
            }
        }
        return crc
    }
}
