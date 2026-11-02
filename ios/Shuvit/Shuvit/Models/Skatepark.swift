import Foundation
import CoreLocation

struct Skatepark: Codable, Identifiable, Hashable {
    let id: UUID
    let name: String
    let slug: String
    let lat: Double
    let lng: Double
    let city: String?
    let state: String?
    let country: String
    let parkType: String?
    let environment: String?
    let rating: Double?
    let difficulty: String?
    let isFree: Bool
    let heroImageUrl: String?
    let verified: Bool
    let distanceKm: Double?

    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: lat, longitude: lng)
    }

    var locationString: String {
        [city, state].compactMap { $0 }.joined(separator: ", ")
    }

    enum CodingKeys: String, CodingKey {
        case id, name, slug, lat, lng, city, state, country, environment, rating, difficulty, verified
        case parkType = "park_type"
        case isFree = "is_free"
        case heroImageUrl = "hero_image_url"
        case distanceKm = "distance_km"
    }
}

typealias SkateparkNear = Skatepark

struct ParkCluster: Codable, Identifiable {
    let count: Int
    let lat: Double
    let lng: Double
    let south: Double
    let north: Double
    let west: Double
    let east: Double

    var id: String { "\(lat),\(lng),\(count)" }

    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: lat, longitude: lng)
    }
}

struct ParkMapResponse: Codable {
    let clusters: [ParkCluster]
    let parks: [Skatepark]
}

struct SkateparkDetail: Codable, Identifiable {
    let id: UUID
    let name: String
    let slug: String
    let lat: Double
    let lng: Double
    let description: String?
    let address: String?
    let city: String?
    let state: String?
    let country: String
    let zipCode: String?
    let parkType: String?
    let environment: String?
    let features: [String: AnyCodable]?
    let rating: Double?
    let difficulty: String?
    let lighting: Bool?
    let isFree: Bool
    let hours: [String: AnyCodable]?
    let surface: String?
    let heroImageUrl: String?
    let verified: Bool
    let dataQualityScore: Double?
    let createdAt: String
    let updatedAt: String
    let media: [MediaItem]

    var coordinate: CLLocationCoordinate2D {
        CLLocationCoordinate2D(latitude: lat, longitude: lng)
    }

    var locationString: String {
        [city, state].compactMap { $0 }.joined(separator: ", ")
    }

    var fullAddress: String? {
        var parts: [String] = []
        if let address, !address.isEmpty { parts.append(address) }
        if let city, !city.isEmpty { parts.append(city) }
        if let state, !state.isEmpty { parts.append(state) }
        if let zipCode, !zipCode.isEmpty { parts.append(zipCode) }
        let result = parts.joined(separator: ", ")
        return result.isEmpty ? nil : result
    }

    enum CodingKeys: String, CodingKey {
        case id, name, slug, lat, lng, description, address, city, state, country, environment
        case rating, difficulty, lighting, hours, surface, verified, media, features
        case zipCode = "zip_code"
        case parkType = "park_type"
        case isFree = "is_free"
        case heroImageUrl = "hero_image_url"
        case dataQualityScore = "data_quality_score"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}

struct AnyCodable: Codable, Hashable {
    let value: Any

    init(_ value: Any) {
        self.value = value
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if let string = try? container.decode(String.self) {
            value = string
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let bool = try? container.decode(Bool.self) {
            value = bool
        } else {
            value = ""
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        if let string = value as? String {
            try container.encode(string)
        } else if let int = value as? Int {
            try container.encode(int)
        } else if let double = value as? Double {
            try container.encode(double)
        } else if let bool = value as? Bool {
            try container.encode(bool)
        }
    }

    static func == (lhs: AnyCodable, rhs: AnyCodable) -> Bool {
        String(describing: lhs.value) == String(describing: rhs.value)
    }

    func hash(into hasher: inout Hasher) {
        hasher.combine(String(describing: value))
    }
}
