import Foundation
import Observation

@Observable
@MainActor
final class AuthManager {
    static let shared = AuthManager()

    private(set) var isAuthenticated = false
    private(set) var currentUser: User?
    private(set) var isLoading = false

    nonisolated private static let tokenKey = "auth_token"

    nonisolated var token: String? {
        KeychainHelper.readString(for: Self.tokenKey)
    }

    /// Read token without needing MainActor isolation
    nonisolated static var currentToken: String? {
        KeychainHelper.readString(for: tokenKey)
    }

    private init() {
        isAuthenticated = token != nil
    }

    func requestMagicLink(email: String) async throws {
        isLoading = true
        defer { isLoading = false }
        try await APIClient.shared.send(.requestMagicLink(email: email))
    }

    func handleCallback(token: String) {
        KeychainHelper.saveString(token, for: Self.tokenKey)
        isAuthenticated = true
        Task { await fetchUser() }
    }

    func handleDeepLink(url: URL) -> Bool {
        guard url.scheme == AppConfig.appScheme,
              url.host == AppConfig.authCallbackPath,
              let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let token = components.queryItems?.first(where: { $0.name == "token" })?.value
        else { return false }

        handleCallback(token: token)
        return true
    }

    func fetchUser() async {
        guard isAuthenticated else { return }
        do {
            let user: User = try await APIClient.shared.request(.me)
            currentUser = user
        } catch {
            // Token might be expired
            if case APIError.unauthorized = error {
                logout()
            }
        }
    }

    func logout() {
        KeychainHelper.delete(for: Self.tokenKey)
        isAuthenticated = false
        currentUser = nil
    }

    func requireAuth(action: @escaping () async -> Void) async {
        if isAuthenticated {
            await action()
        }
        // If not authenticated, the UI should show login
    }
}
