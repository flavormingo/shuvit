import Foundation

enum APIError: LocalizedError {
    case invalidURL
    case unauthorized
    case serverError(Int, String?)
    case decodingError(Error)
    case networkError(Error)

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid URL"
        case .unauthorized: return "Please sign in again."
        case .serverError(let code, let body):
            return Self.detail(from: body) ?? "Something went wrong (\(code)). Please try again."
        case .decodingError: return "Something went wrong reading the response."
        case .networkError(let err): return err.localizedDescription
        }
    }

    /// The API sends human-readable errors as {"detail": "..."}.
    private static func detail(from body: String?) -> String? {
        guard let data = body?.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return nil }
        return json["detail"] as? String
    }
}

final class APIClient {
    static let shared = APIClient()

    private let session: URLSession
    private let uploadSession: URLSession
    private let decoder = JSONDecoder()

    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 60
        self.session = URLSession(configuration: config)

        // A video on a slow connection can take minutes to send.
        let uploadConfig = URLSessionConfiguration.default
        uploadConfig.timeoutIntervalForRequest = 120
        uploadConfig.timeoutIntervalForResource = 600
        self.uploadSession = URLSession(configuration: uploadConfig)
    }

    func request<T: Decodable>(_ endpoint: Endpoint) async throws -> T {
        try decode(try await perform(try makeRequest(endpoint), using: session))
    }

    /// For requests whose response body doesn't matter.
    func send(_ endpoint: Endpoint) async throws {
        _ = try await perform(try makeRequest(endpoint), using: session)
    }

    func upload<T: Decodable>(
        path: String,
        fileData: Data,
        fileName: String,
        mimeType: String,
        fields: [String: String] = [:]
    ) async throws -> T {
        guard let url = URL(string: AppConfig.apiBaseURL + "/api/v1" + path) else {
            throw APIError.invalidURL
        }

        let boundary = UUID().uuidString
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        if let token = AuthManager.currentToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        var body = Data()
        for (key, value) in fields {
            body.append(Data("--\(boundary)\r\n".utf8))
            body.append(Data("Content-Disposition: form-data; name=\"\(key)\"\r\n\r\n".utf8))
            body.append(Data("\(value)\r\n".utf8))
        }

        body.append(Data("--\(boundary)\r\n".utf8))
        body.append(Data("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileName)\"\r\n".utf8))
        body.append(Data("Content-Type: \(mimeType)\r\n\r\n".utf8))
        body.append(fileData)
        body.append(Data("\r\n--\(boundary)--\r\n".utf8))
        request.httpBody = body

        return try decode(try await perform(request, using: uploadSession))
    }

    private func makeRequest(_ endpoint: Endpoint) throws -> URLRequest {
        guard let url = endpoint.url else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = endpoint.method.rawValue

        if let body = endpoint.body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }

        // Public endpoints use the token when there is one, for example to hide
        // media from users this person has blocked.
        if let token = AuthManager.currentToken {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        } else if endpoint.requiresAuth {
            throw APIError.unauthorized
        }

        return request
    }

    private func perform(_ request: URLRequest, using session: URLSession) async throws -> Data {
        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw APIError.networkError(error)
        }

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.networkError(URLError(.badServerResponse))
        }

        if httpResponse.statusCode == 401 {
            await MainActor.run { AuthManager.shared.logout() }
            throw APIError.unauthorized
        }

        guard (200..<300).contains(httpResponse.statusCode) else {
            throw APIError.serverError(httpResponse.statusCode, String(data: data, encoding: .utf8))
        }

        return data
    }

    private func decode<T: Decodable>(_ data: Data) throws -> T {
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decodingError(error)
        }
    }
}
