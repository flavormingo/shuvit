import CoreLocation
import MapKit
import Observation

struct ParkFilters: Equatable {
    var environment: String?
    var price: String?

    var isFree: Bool? {
        switch price {
        case "free": return true
        case "paid": return false
        default: return nil
        }
    }

    var activeCount: Int {
        [environment, price].compactMap { $0 }.count
    }
}

struct PlaceResult: Identifiable {
    let id = UUID()
    let name: String
    let subtitle: String
    let region: MKCoordinateRegion
}

@Observable
@MainActor
final class MapViewModel {
    var parks: [Skatepark] = []
    var clusters: [ParkCluster] = []
    var errorMessage: String?

    var parkResults: [Skatepark] = []
    var placeResults: [PlaceResult] = []
    private(set) var isSearching = false
    private(set) var hasSearched = false

    private static let cellsAcrossScreen = 6.0
    private static let smallestCell = 0.0001

    private var loadedBounds: Bounds?
    private var loadedCell: Double?
    private var loadedFilters: ParkFilters?
    private var fetchTask: Task<Void, Never>?

    func load(region: MKCoordinateRegion, filters: ParkFilters) {
        let cell = Self.cellSize(for: region)
        if let loadedBounds, loadedCell == cell, loadedFilters == filters,
           loadedBounds.contains(Bounds(region: region)) {
            return
        }

        let padded = Bounds(region: region, scale: 1.4)
        fetchTask?.cancel()
        fetchTask = Task {
            try? await Task.sleep(for: .milliseconds(250))
            guard !Task.isCancelled else { return }
            await fetch(bounds: padded, cell: cell, filters: filters)
        }
    }

    private func fetch(bounds: Bounds, cell: Double, filters: ParkFilters) async {
        do {
            let response: ParkMapResponse = try await APIClient.shared.request(
                .parksMap(
                    south: bounds.south,
                    west: bounds.west,
                    north: bounds.north,
                    east: bounds.east,
                    cell: cell,
                    environment: filters.environment,
                    isFree: filters.isFree
                )
            )
            guard !Task.isCancelled else { return }
            parks = response.parks
            clusters = response.clusters
            loadedBounds = bounds
            loadedCell = cell
            loadedFilters = filters
            errorMessage = nil
        } catch {
            guard !Task.isCancelled else { return }
            errorMessage = error.localizedDescription
        }
    }

    func search(query: String) async {
        isSearching = true
        defer { isSearching = false }

        async let places = Self.findPlaces(matching: query)
        do {
            parkResults = try await APIClient.shared.request(.parks(limit: 20, q: query))
            errorMessage = nil
        } catch {
            parkResults = []
            errorMessage = error.localizedDescription
        }
        placeResults = await places
        hasSearched = true
    }

    func clearSearch() {
        parkResults = []
        placeResults = []
        hasSearched = false
    }

    private static func findPlaces(matching query: String) async -> [PlaceResult] {
        let request = MKLocalSearch.Request()
        request.naturalLanguageQuery = query
        request.resultTypes = .address

        guard let response = try? await MKLocalSearch(request: request).start() else { return [] }

        return response.mapItems.prefix(3).map { item in
            let radius = (item.placemark.region as? CLCircularRegion)?.radius ?? 5000
            let meters = max(radius * 2.5, 8000)
            return PlaceResult(
                name: item.name ?? query,
                subtitle: item.placemark.title ?? "",
                region: MKCoordinateRegion(
                    center: item.placemark.coordinate,
                    latitudinalMeters: meters,
                    longitudinalMeters: meters
                )
            )
        }
    }

    private static func cellSize(for region: MKCoordinateRegion) -> Double {
        let target = region.span.longitudeDelta / cellsAcrossScreen
        var cell = 90.0
        while cell > target && cell > smallestCell {
            cell /= 2
        }
        return cell
    }
}

private struct Bounds {
    let south: Double
    let west: Double
    let north: Double
    let east: Double

    init(region: MKCoordinateRegion, scale: Double = 1) {
        let latHalf = region.span.latitudeDelta * scale / 2
        let lngHalf = region.span.longitudeDelta * scale / 2
        south = max(region.center.latitude - latHalf, -90)
        north = min(region.center.latitude + latHalf, 90)

        if lngHalf >= 180 {
            west = -180
            east = 180
        } else {
            west = Self.wrap(region.center.longitude - lngHalf)
            east = Self.wrap(region.center.longitude + lngHalf)
        }
    }

    private static func wrap(_ longitude: Double) -> Double {
        var value = longitude
        if value > 180 { value -= 360 }
        if value < -180 { value += 360 }
        return value
    }

    private var crossesAntimeridian: Bool { west > east }

    func contains(_ other: Bounds) -> Bool {
        guard south <= other.south, north >= other.north else { return false }
        guard !crossesAntimeridian, !other.crossesAntimeridian else { return false }
        return west <= other.west && east >= other.east
    }
}
