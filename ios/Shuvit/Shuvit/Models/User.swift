import Foundation

struct User: Codable, Identifiable {
    let id: UUID
    let email: String
    let displayName: String?
    let avatarUrl: String?
    let isAdmin: Bool
    let createdAt: String

    enum CodingKeys: String, CodingKey {
        case id, email
        case displayName = "display_name"
        case avatarUrl = "avatar_url"
        case isAdmin = "is_admin"
        case createdAt = "created_at"
    }
}

struct UserProfile: Codable, Identifiable {
    let id: UUID
    let displayName: String?
    let avatarUrl: String?
    let approvedCount: Int
    let parksCount: Int
    let rank: String

    var avatarFullURL: URL? {
        guard let url = avatarUrl else { return nil }
        return URL(string: AppConfig.apiBaseURL + url)
    }

    enum CodingKeys: String, CodingKey {
        case id
        case displayName = "display_name"
        case avatarUrl = "avatar_url"
        case approvedCount = "approved_count"
        case parksCount = "parks_count"
        case rank
    }
}

struct UserStats: Codable {
    let approvedCount: Int
    let rank: String
    let nextRank: String?
    let progress: Double
    let nextThreshold: Int?

    enum CodingKeys: String, CodingKey {
        case approvedCount = "approved_count"
        case rank
        case nextRank = "next_rank"
        case progress
        case nextThreshold = "next_threshold"
    }
}

struct Contribution: Codable, Identifiable {
    let id: UUID
    let parkId: UUID
    let parkName: String
    let mediaType: String
    let fileUrl: String
    let thumbnailUrl: String?
    let description: String?
    let submittedAt: String

    var fullThumbnailURL: URL? {
        guard let thumb = thumbnailUrl else { return nil }
        return URL(string: AppConfig.apiBaseURL + thumb)
    }

    enum CodingKeys: String, CodingKey {
        case id, description
        case parkId = "park_id"
        case parkName = "park_name"
        case mediaType = "media_type"
        case fileUrl = "file_url"
        case thumbnailUrl = "thumbnail_url"
        case submittedAt = "submitted_at"
    }
}
