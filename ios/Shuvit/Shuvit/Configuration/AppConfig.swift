import Foundation

enum AppConfig {
    static var apiBaseURL: String {
        Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String
            ?? "https://api.shuvit.app"
    }

    static let appScheme = "shuvit"
    static let authCallbackPath = "auth"

    static let privacyURL = URL(string: "https://shuvit.app/privacy")!
    static let termsURL = URL(string: "https://shuvit.app/terms")!
    static let osmCopyrightURL = URL(string: "https://www.openstreetmap.org/copyright")!

    static var appVersion: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? ""
    }
}
