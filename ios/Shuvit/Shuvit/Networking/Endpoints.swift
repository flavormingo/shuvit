import Foundation

enum HTTPMethod: String {
    case get = "GET"
    case post = "POST"
    case patch = "PATCH"
    case delete = "DELETE"
}

struct Endpoint {
    let path: String
    let method: HTTPMethod
    let queryItems: [URLQueryItem]?
    let body: Data?
    let requiresAuth: Bool

    init(
        path: String,
        method: HTTPMethod = .get,
        queryItems: [URLQueryItem]? = nil,
        body: Data? = nil,
        requiresAuth: Bool = false
    ) {
        self.path = path
        self.method = method
        self.queryItems = queryItems
        self.body = body
        self.requiresAuth = requiresAuth
    }

    var url: URL? {
        var components = URLComponents(string: AppConfig.apiBaseURL + "/api/v1" + path)
        components?.queryItems = queryItems
        return components?.url
    }
}

// MARK: - Park Endpoints

extension Endpoint {
    static func parks(page: Int = 1, limit: Int = 50, city: String? = nil, q: String? = nil) -> Endpoint {
        var items = [
            URLQueryItem(name: "page", value: "\(page)"),
            URLQueryItem(name: "limit", value: "\(limit)"),
        ]
        if let city { items.append(URLQueryItem(name: "city", value: city)) }
        if let q { items.append(URLQueryItem(name: "q", value: q)) }

        return Endpoint(path: "/parks", queryItems: items)
    }

    static func parksNear(lat: Double, lng: Double, radiusKm: Double = 25, limit: Int = 50) -> Endpoint {
        Endpoint(
            path: "/parks/near",
            queryItems: [
                URLQueryItem(name: "lat", value: "\(lat)"),
                URLQueryItem(name: "lng", value: "\(lng)"),
                URLQueryItem(name: "radius_km", value: "\(radiusKm)"),
                URLQueryItem(name: "limit", value: "\(limit)"),
            ]
        )
    }

    static func parkDetail(id: UUID) -> Endpoint {
        Endpoint(path: "/parks/\(id)")
    }
}

// MARK: - Auth Endpoints

extension Endpoint {
    static func requestMagicLink(email: String) -> Endpoint {
        let body = try? JSONEncoder().encode(["email": email])
        return Endpoint(path: "/auth/request-magic-link", method: .post, body: body)
    }

    static func verifyOTP(email: String, code: String) -> Endpoint {
        let body = try? JSONEncoder().encode(["email": email, "code": code])
        return Endpoint(path: "/auth/verify-otp", method: .post, body: body)
    }
}

// MARK: - User Endpoints

extension Endpoint {
    static var me: Endpoint {
        Endpoint(path: "/user/me", requiresAuth: true)
    }

    static func updateMe(displayName: String) -> Endpoint {
        let body = try? JSONEncoder().encode(["display_name": displayName])
        return Endpoint(path: "/user/me", method: .patch, body: body, requiresAuth: true)
    }

    static var myStats: Endpoint {
        Endpoint(path: "/user/me/stats", requiresAuth: true)
    }

    static var myContributions: Endpoint {
        Endpoint(path: "/user/me/contributions", requiresAuth: true)
    }

    static func userProfile(id: UUID) -> Endpoint {
        Endpoint(path: "/user/\(id)/profile")
    }

    static func userContributions(id: UUID) -> Endpoint {
        Endpoint(path: "/user/\(id)/contributions")
    }
}

// MARK: - Favorites Endpoints

extension Endpoint {
    static var favorites: Endpoint {
        Endpoint(path: "/favorites", requiresAuth: true)
    }

    static func addFavorite(parkId: UUID) -> Endpoint {
        let body = try? JSONEncoder().encode(["park_id": parkId.uuidString])
        return Endpoint(path: "/favorites", method: .post, body: body, requiresAuth: true)
    }

    static func removeFavorite(parkId: UUID) -> Endpoint {
        Endpoint(path: "/favorites/\(parkId)", method: .delete, requiresAuth: true)
    }
}

// MARK: - Media Endpoints

extension Endpoint {
    static func parkMedia(parkId: UUID) -> Endpoint {
        Endpoint(path: "/parks/\(parkId)/media")
    }
}
