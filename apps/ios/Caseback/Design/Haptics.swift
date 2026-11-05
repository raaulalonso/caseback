import UIKit
import CoreGraphics

/// Haptics as typography (the design notes §2): present, consistent, unnoticed.
@MainActor
enum Haptics {
    private static let soft = UIImpactFeedbackGenerator(style: .soft)
    private static let light = UIImpactFeedbackGenerator(style: .light)
    private static let medium = UIImpactFeedbackGenerator(style: .medium)
    private static let selection = UISelectionFeedbackGenerator()
    private static let rigid = UIImpactFeedbackGenerator(style: .rigid)
    private static let notification = UINotificationFeedbackGenerator()

    static func prepare() {
        soft.prepare(); light.prepare(); selection.prepare(); notification.prepare()
    }

    /// The click of a detent: the pull has gone far enough and will now open.
    static func detent() { rigid.impactOccurred(intensity: 0.9) }
    /// Resistance under the finger: a soft tick that gets firmer the further the pull has gone.
    static func friction(_ amount: CGFloat) { soft.impactOccurred(intensity: 0.25 + 0.6 * min(max(amount, 0), 1)) }

    static func tap() { light.impactOccurred(intensity: 0.7) }
    static func step() { soft.impactOccurred() }
    static func tick() { selection.selectionChanged() }
    static func thud() { medium.impactOccurred(intensity: 0.8) }
    static func success() { notification.notificationOccurred(.success) }
    static func warning() { notification.notificationOccurred(.warning) }
}
