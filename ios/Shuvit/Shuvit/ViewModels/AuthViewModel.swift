import Foundation
import Observation

@Observable
@MainActor
final class AuthViewModel {
    var email = ""
    var otpCode = ""
    var isLoading = false
    var codeSent = false
    var errorMessage: String?

    func sendCode() async {
        email = email.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !email.isEmpty else {
            errorMessage = "Please enter your email"
            return
        }

        isLoading = true
        errorMessage = nil

        do {
            try await AuthManager.shared.requestMagicLink(email: email)
            codeSent = true
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    func verifyCode() async {
        let code = otpCode.trimmingCharacters(in: .whitespacesAndNewlines)
        guard code.count == 6 else {
            errorMessage = "Enter the 6-digit code"
            return
        }

        isLoading = true
        errorMessage = nil

        do {
            let response: TokenResponse = try await APIClient.shared.request(
                .verifyOTP(email: email, code: code)
            )
            AuthManager.shared.handleCallback(token: response.accessToken)
        } catch {
            errorMessage = "Invalid or expired code. Try again."
        }

        isLoading = false
    }
}

private struct TokenResponse: Decodable {
    let accessToken: String
    let tokenType: String

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case tokenType = "token_type"
    }
}
