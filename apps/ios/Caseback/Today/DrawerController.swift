import CoreGraphics
import Foundation
import Observation
import SwiftUI

/// The pull that opens the conclusions sheet. Not a scroll: the finger meets resistance, feels a soft tick for every few
/// points of travel (firmer as it goes), and a click when it passes the detent, after which the sheet comes with it and
/// settles on a spring. Let go before the click and it falls back with a bounce. The mapping is pure so it can be tested.
enum PullResistance {
    /// Travel of the finger, in points, before the detent clicks.
    static let detent: CGFloat = 36
    /// How much of the finger's travel the sheet follows while it resists.
    static let resisted: CGFloat = 0.55
    /// After the click the sheet runs a little ahead of the finger.
    static let released: CGFloat = 1.3
    /// A finger speed, in points per second, that opens or closes the sheet even before the detent.
    static let flick: CGFloat = 380

    /// How far the sheet has moved for a finger travel of `t` points.
    static func displacement(_ t: CGFloat) -> CGFloat {
        let t = max(t, 0)
        return t <= detent ? t * resisted : detent * resisted + (t - detent) * released
    }

    /// A gentle but clearly intended pull (this far, this fast) also counts, so it never needs a second try.
    static let gentle: (travel: CGFloat, velocity: CGFloat) = (18, 150)

    static func committed(travel t: CGFloat, velocity: CGFloat) -> Bool {
        t >= detent || velocity > flick || (t >= gentle.travel && velocity > gentle.velocity)
    }
}

@MainActor
@Observable
final class DrawerController {
    /// 0 closed, 1 open. Set without animation while the finger is down, with a spring when it lets go.
    var progress: CGFloat = 0
    private(set) var isOpen = false
    private(set) var isDragging = false
    /// Reported by the sheet's scroll view: a downward pull only closes the sheet when the content is at its top.
    var scrollAtTop = true
    var scrollOffset: CGFloat = 0
    /// Distance, in points, from closed to open. Set by the layout.
    var distance: CGFloat = 600

    private var startedOpen = false
    private var lastTickBucket = -1
    private var clicked = false

    /// Whether a drag should drive the sheet. Decided once, when the finger has travelled far enough to tell its direction.
    /// `atTop` is where the sheet's content was when the finger went down: scrolling it back up must not close the sheet on
    /// the way, even if the content reaches the top while the finger is still moving.
    func accepts(dx: CGFloat, dy: CGFloat, atTop: Bool? = nil) -> Bool {
        guard abs(dy) > abs(dx) else { return false }
        return isOpen ? (dy > 0 && (atTop ?? scrollAtTop)) : dy < 0
    }

    func begin() {
        isDragging = true
        startedOpen = isOpen
        lastTickBucket = -1
        clicked = false
        Haptics.prepare()
    }

    /// `travel` is the finger's travel in the direction that opens (up) or closes (down), always positive.
    func drag(travel t: CGFloat) {
        guard isDragging else { return }
        let moved = PullResistance.displacement(t) / max(distance, 1)
        progress = startedOpen ? 1 - min(moved, 1) : min(moved, 1)
        // Friction: a tick every 9 pt inside the resistance, firmer with distance.
        if t < PullResistance.detent {
            let bucket = Int(t / 9)
            if bucket != lastTickBucket, bucket > 0 {
                lastTickBucket = bucket
                Haptics.friction(t / PullResistance.detent)
            }
        } else if !clicked {
            clicked = true
            Haptics.detent()
        }
    }

    func end(travel t: CGFloat, velocity: CGFloat) {
        guard isDragging else { return }
        isDragging = false
        if PullResistance.committed(travel: t, velocity: velocity) {
            startedOpen ? close() : open()
        } else {
            // Not far enough: it falls back with a bounce.
            snap(to: startedOpen ? 1 : 0, response: 0.5, damping: 0.55)
        }
    }

    /// Debug: jump to a progress value.
    func preview(_ value: CGFloat) {
        progress = value
        isOpen = value >= 1
    }

    func open() {
        isOpen = true
        snap(to: 1, response: 0.62, damping: 0.8)
        Haptics.step()
    }

    func close() {
        isOpen = false
        snap(to: 0, response: 0.55, damping: 0.78)
        Haptics.step()
    }

    private func snap(to value: CGFloat, response: Double, damping: Double) {
        withAnimation(.spring(response: response, dampingFraction: damping)) { progress = value }
    }
}
