import SwiftUI

// Two families, each with one job (02 §2): IBM Plex Mono for every number, unit, time and the wordmark;
// SF Pro for sentences so Dynamic Type, Bold Text and VoiceOver behave.

enum PlexMono {
    case light, regular, medium

    var name: String {
        switch self {
        case .light: return "IBMPlexMono-Light"
        case .regular: return "IBMPlexMono-Regular"
        case .medium: return "IBMPlexMono-Medium"
        }
    }
}

extension Font {
    /// Numeric face. `relativeTo` makes it scale with Dynamic Type.
    static func mono(_ weight: PlexMono, _ size: CGFloat, relativeTo style: Font.TextStyle = .body) -> Font {
        .custom(weight.name, size: size, relativeTo: style)
    }

    /// A fixed size, for drawings that scale as a whole (the Today panel scales each block to the screen).
    static func monoFixed(_ weight: PlexMono, _ size: CGFloat) -> Font { .custom(weight.name, fixedSize: size) }

    static let numHero = Font.mono(.light, 88, relativeTo: .largeTitle)
    static let numL = Font.mono(.light, 56, relativeTo: .largeTitle)
    static let numM = Font.mono(.regular, 34, relativeTo: .title)
    static let numS = Font.mono(.regular, 22, relativeTo: .title3)
    static let unit = Font.mono(.regular, 13, relativeTo: .footnote)
    static let axis = Font.mono(.regular, 11, relativeTo: .caption2)
    static let wordmark = Font.mono(.medium, 15, relativeTo: .body)

    // Sentences use the system text styles so they follow Dynamic Type; the sizes match 02-visual-system.md at the default.
    static let title = Font.largeTitle.weight(.medium)  // 34
    static let body = Font.body  // 17
    static let callout = Font.callout  // 16
    static let label = Font.footnote.weight(.medium)  // 13
}
