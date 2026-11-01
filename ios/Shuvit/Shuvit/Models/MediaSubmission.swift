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
