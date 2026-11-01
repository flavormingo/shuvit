import Foundation

enum AppConfig {
    static var apiBaseURL: String {
        Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String
            ?? "https://api.shuvit.app"
    }

    static let appScheme = "shuvit"
    static let authCallbackPath = "auth"
}
