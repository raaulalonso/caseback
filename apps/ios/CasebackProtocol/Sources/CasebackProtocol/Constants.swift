import Foundation

// Framing (spec/framing.md)
public let CasebackMagic: UInt8 = 0xA5
public let CasebackProtoVer: UInt8 = 0x01
public let CasebackHeaderLen = 5
public let CASEBACKCRCLen = 2
public let CasebackMaxFrame = 182  // ATT_MTU 185 - 3
public let CasebackMaxPayload = CasebackMaxFrame - CasebackHeaderLen - CASEBACKCRCLen  // 175

// Message types (spec/messages.md)
public let MSGInfoRequest: UInt8 = 0x01
public let MSGInfoResponse: UInt8 = 0x02
public let MSGError: UInt8 = 0x03
public let MSGTimeAnchor: UInt8 = 0x04
public let MSGStreamData: UInt8 = 0x10
public let MSGStreamControl: UInt8 = 0x11
public let MSGHistoryQuery: UInt8 = 0x12
public let MSGHistoryAck: UInt8 = 0x13
public let MSGConfigSet: UInt8 = 0x20
public let MSGConfigState: UInt8 = 0x21
public let MSGBattery: UInt8 = 0x22
public let MSGDFUReservedFirst: UInt8 = 0x30  // 0x30...0x3F: standard SMP DFU
public let MSGDFUReservedLast: UInt8 = 0x3F

// Capability bits
public let CAPPPGRaw: UInt32 = 1 << 0
public let CAPPPGSummary: UInt32 = 1 << 1
public let CAPAccel: UInt32 = 1 << 2
public let CAPSpO2: UInt32 = 1 << 3
public let CAPTemperature: UInt32 = 1 << 4
public let CAPDFUSMP: UInt32 = 1 << 5
public let CAPIBILog: UInt32 = 1 << 6
public let CAPEncryptedOnly: UInt32 = 1 << 7

// Config enums
public let ModeNight: UInt8 = 0
public let ModeDay: UInt8 = 1
public let ModeWorkout: UInt8 = 2
public let ModeRaw: UInt8 = 3
public let PayloadFormatSummary: UInt8 = 0
public let PayloadFormatStreamRaw: UInt8 = 1
public let LEDGreen: UInt8 = 1 << 0
public let LEDRed: UInt8 = 1 << 1
public let LEDIR: UInt8 = 1 << 2
public let MaxPPGRateHz: UInt16 = 400
public let ChargingNotCharging: UInt8 = 0
public let ChargingCharging: UInt8 = 1
public let ChargingComplete: UInt8 = 2
public let ChargingFault: UInt8 = 3
public let ChargingUnknown: UInt8 = 0xFF
public let PercentUnknown: UInt8 = 0xFF
public let CurrentUnknown: UInt16 = 0xFFFF

// GATT (spec/gatt.md)
public let GATTServiceUUID = "decdc7df-2ecb-4d75-b44c-992dccdfca5b"
public let GATTInfoUUID = "decdc7e0-2ecb-4d75-b44c-992dccdfca5b"
public let GATTControlUUID = "decdc7e1-2ecb-4d75-b44c-992dccdfca5b"
public let GATTDataUUID = "decdc7e2-2ecb-4d75-b44c-992dccdfca5b"
public let GATTSMPServiceUUID = "8d53dc1d-1db7-4cd3-868b-8a527460aa84"
public let GATTSMPCharacteristicUUID = "da2e7828-fbce-4e01-ae9e-261174997c48"

public let ConnIntervalMinMs = 1000
public let ConnIntervalMaxMs = 1500
public let ConnLatency = 0
public let ConnSupervisionTimeoutMs = 6000
public let ATTMTURequested = 247
