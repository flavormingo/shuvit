import Foundation

struct MediaItem: Codable, Identifiable, Hashable {
    let id: UUID
    let parkId: UUID
    let userId: UUID
    let mediaType: String
    let fileUrl: String
    let thumbnailUrl: String?
    let description: String?
    let tags: [String]?
    let status: String
    let submittedAt: String
    let contributorName: String?

    var fullFileURL: URL? {
        URL(string: AppConfig.apiBaseURL + fileUrl)
    }

    var fullThumbnailURL: URL? {
        guard let thumb = thumbnailUrl else { return fullFileURL }
        return URL(string: AppConfig.apiBaseURL + thumb)
    }

    enum CodingKeys: String, CodingKey {
        case id, description, tags, status
        case contributorName = "contributor_name"
        case parkId = "park_id"
        case userId = "user_id"
        case mediaType = "media_type"
        case fileUrl = "file_url"
        case thumbnailUrl = "thumbnail_url"
        case submittedAt = "submitted_at"
    }
}

/// A submission waiting for an admin, or approved media that someone reported.
struct ReviewItem: Codable, Identifiable {
    let id: UUID
    let parkId: UUID
    let parkName: String
    let userId: UUID
    let contributorName: String?
    let mediaType: String
    let fileUrl: String
    let thumbnailUrl: String?
    let description: String?
    let status: String
    let reportCount: Int

    var fullFileURL: URL? {
        URL(string: AppConfig.apiBaseURL + fileUrl)
    }

    enum CodingKeys: String, CodingKey {
        case id, description, status
        case parkId = "park_id"
        case parkName = "park_name"
        case userId = "user_id"
        case contributorName = "contributor_name"
        case mediaType = "media_type"
        case fileUrl = "file_url"
        case thumbnailUrl = "thumbnail_url"
        case reportCount = "report_count"
    }
}

struct Favorite: Codable, Identifiable {
    let id: UUID
    let parkId: UUID
    let createdAt: String
    let park: Skatepark?

    enum CodingKeys: String, CodingKey {
        case id, park
        case parkId = "park_id"
        case createdAt = "created_at"
    }
}
