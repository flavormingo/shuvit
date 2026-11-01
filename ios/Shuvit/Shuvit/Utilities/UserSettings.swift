import Foundation
import Observation

@Observable
final class UserSettings {
    static let shared = UserSettings()

    var useMiles: Bool {
        didSet { UserDefaults.standard.set(useMiles, forKey: "useMiles") }
    }

    private init() {
        // Default to miles for US users, km for everyone else
        if UserDefaults.standard.object(forKey: "useMiles") != nil {
            self.useMiles = UserDefaults.standard.bool(forKey: "useMiles")
        } else {
            self.useMiles = Locale.current.measurementSystem == .us
        }
    }

    func formatDistance(km: Double) -> String {
        if useMiles {
            let miles = km * 0.621371
            if miles < 0.1 {
                return String(format: "%.0f ft", miles * 5280)
            }
            return String(format: "%.1f mi", miles)
        } else {
            if km < 1 {
                return String(format: "%.0f m", km * 1000)
            }
            return String(format: "%.1f km", km)
        }
    }
}
