import SwiftUI

// Design tokens. Source of truth: the design notes. A literal outside this file is a bug
// (the design notes, rule D1).

enum Palette {
    static let ground = Color(hex: 0x000000)
    static let text1 = Color(hex: 0xFFFFFF)
    static let text2 = Color(hex: 0xB8B8B8)
    static let text3 = Color(hex: 0x8C8C8C)
    static let hairline = Color.white.opacity(0.14)
    /// The ground of a dashboard block (D35): one step above black, no border, no shadow.
    static let tile = Color(hex: 0x131316)
    /// A pressable row on the black: one step lighter than the sheet ground, rounded, no border (Device).
    static let control = Color(hex: 0x1C1C20)
    static let alert = Color(hex: 0xFF4D3D)
    /// Sleep stages sit inside the sleep hue (02 section 1); wake is not a colour, it is drawn as an outline.
    static let stageDeep = Color(hex: 0x3A4FE0)
    static let stageLight = Color(hex: 0x4D6BFF)
    static let stageRem = Color(hex: 0x8FA8FF)
}

/// One fixed colour per metric. Colour is identity, never certainty and never good/bad.
enum Metric: Int, CaseIterable, Identifiable {
    // The order is the blob order of the onboarding field (02 §10).
    case heartRate, hrv, sleep, readiness, steps, spo2, skinTemp

    var id: Int { rawValue }

    var color: Color { Color(hex: hex) }

    var hex: UInt32 {
        switch self {
        case .heartRate: return 0xFF4F7B
        case .hrv: return 0xD79BFF
        case .sleep: return 0x4D6BFF
        case .readiness: return 0xEEF24B
        case .steps: return 0x3DDC84
        case .spo2: return 0x3CC8F5
        case .skinTemp: return 0xFF9A3D
        }
    }

    /// Shape index shared with the Metal shader: 0 circle, 1 diamond, 2 square, 3 triangle up, 4 open circle,
    /// 5 triangle down, 6 bar.
    var markKind: Float {
        switch self {
        case .heartRate: return 0
        case .hrv: return 1
        case .sleep: return 2
        case .steps: return 3
        case .spo2: return 4
        case .skinTemp: return 5
        case .readiness: return 6
        }
    }

    /// Metrics whose Health samples the app writes (D13, D17): SpO2 is never written.
    var writtenToHealth: Bool { self != .spo2 && self != .skinTemp && self != .readiness }
}

enum Space {
    static let s4: CGFloat = 4
    static let s8: CGFloat = 8
    static let s12: CGFloat = 12
    static let s16: CGFloat = 16
    static let s20: CGFloat = 20
    static let s24: CGFloat = 24
    static let s32: CGFloat = 32
    static let s48: CGFloat = 48
    static let s64: CGFloat = 64
    static let margin: CGFloat = 20
    static let radius: CGFloat = 2
    static let hit: CGFloat = 44
}

enum Radius {
    /// Continuous corners of a dashboard block; the hero block is rounder.
    static let tile: CGFloat = 28
    static let hero: CGFloat = 34
}

enum Motion {
    static let tap: Double = 0.10
    static let state: Double = 0.24
    static let draw: Double = 0.40
    /// cubic-bezier(0.2, 0, 0, 1)
    static let standard = Animation.timingCurve(0.2, 0, 0, 1, duration: state)
    static func standard(_ duration: Double) -> Animation { .timingCurve(0.2, 0, 0, 1, duration: duration) }
}

extension Color {
    init(hex: UInt32) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: 1)
    }
}
