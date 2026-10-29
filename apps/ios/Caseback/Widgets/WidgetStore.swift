import Foundation

/// The snapshot, shared between the app and the widget extension through an App Group. The app is the only writer; a widget never
/// opens Bluetooth, HealthKit or the network, it reads this file.
enum WidgetStore {
    static let group = "group.com.raaulalonso.caseback"
    private static let fileName = "widget-snapshot.json"
    /// Shared copy when no App Group container exists (an unsigned simulator build): the same suite, in user defaults.
    private static let defaultsKey = "widget.snapshot"

    private static var fileURL: URL? {
        FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: group)?.appendingPathComponent(fileName)
    }

    private static var encoder: JSONEncoder {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        return e
    }

    private static var decoder: JSONDecoder {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }

    @discardableResult
    static func write(_ snapshot: WidgetSnapshot) -> Bool {
        guard let data = try? encoder.encode(snapshot) else { return false }
        if let url = fileURL {
            // Readable after the first unlock, so a widget can draw on a locked phone.
            return (try? data.write(to: url, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])) != nil
        }
        UserDefaults(suiteName: group)?.set(data, forKey: defaultsKey)
        return UserDefaults(suiteName: group) != nil
    }

    static func read() -> WidgetSnapshot? {
        if let url = fileURL, let data = try? Data(contentsOf: url) { return try? decoder.decode(WidgetSnapshot.self, from: data) }
        if let data = UserDefaults(suiteName: group)?.data(forKey: defaultsKey) { return try? decoder.decode(WidgetSnapshot.self, from: data) }
        return nil
    }

    static func clear() {
        if let url = fileURL { try? FileManager.default.removeItem(at: url) }
        UserDefaults(suiteName: group)?.removeObject(forKey: defaultsKey)
    }
}
