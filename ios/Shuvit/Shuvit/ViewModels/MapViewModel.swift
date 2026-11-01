import CoreLocation
import MapKit
import Observation

@Observable
@MainActor
final class MapViewModel {
    var parks: [Skatepark] = []
    var isLoading = false
    var errorMessage: String?
    private(set) var isShowingSearchResults = false

    private static let fetchLimit = 300

    private var fetchedBounds: Bounds?
    private var lastFetchWasTruncated = false
    private var fetchTask: Task<Void, Never>?

    /// Load parks for what's on screen, unless search results are being shown.
    func loadVisible(region: MKCoordinateRegion) {
        guard !isShowingSearchResults else { return }

        let visible = Bounds(region: region)
        // Moving around inside an area we already have needs no new request. If the
        // last result hit the limit, zooming in can reveal parks that were cut off.
        if let fetchedBounds, !lastFetchWasTruncated, fetchedBounds.contains(visible) {
            return
        }

        // Fetch a little beyond the screen so small pans don't refetch.
        let padded = Bounds(region: region, scale: 1.3)
        fetchTask?.cancel()
        fetchTask = Task {
            try? await Task.sleep(for: .milliseconds(300))
            guard !Task.isCancelled else { return }
            await fetchParks(in: padded)
        }
    }

    private func fetchParks(in bounds: Bounds) async {
        isLoading = true
        defer { isLoading = false }

        do {
            let results: [Skatepark] = try await APIClient.shared.request(
                .parksInBounds(
                    south: bounds.south,
                    west: bounds.west,
                    north: bounds.north,
                    east: bounds.east,
                    limit: Self.fetchLimit
                )
            )
            guard !Task.isCancelled, !isShowingSearchResults else { return }
            parks = results
            fetchedBounds = bounds
            lastFetchWasTruncated = results.count >= Self.fetchLimit
            errorMessage = nil
        } catch {
            guard !Task.isCancelled else { return }
            errorMessage = error.localizedDescription
        }
    }

    /// Show matching parks and return a region that fits them.
    func search(query: String) async -> MKCoordinateRegion? {
        fetchTask?.cancel()
        isLoading = true
        defer { isLoading = false }

        do {
            let results: [Skatepark] = try await APIClient.shared.request(.parks(q: query))
            parks = results
            isShowingSearchResults = true
            errorMessage = results.isEmpty ? "No parks found for \"\(query)\"" : nil
            return Self.regionFitting(results)
        } catch {
            errorMessage = error.localizedDescription
            return nil
        }
    }

    /// Leave search and go back to showing what's on screen.
    func clearSearch(region: MKCoordinateRegion?) {
        isShowingSearchResults = false
        errorMessage = nil
        fetchedBounds = nil
        if let region {
            loadVisible(region: region)
        }
    }

    private static func regionFitting(_ parks: [Skatepark]) -> MKCoordinateRegion? {
        guard let first = parks.first else { return nil }
        var south = first.lat, north = first.lat, west = first.lng, east = first.lng
        for park in parks {
            south = min(south, park.lat)
            north = max(north, park.lat)
            west = min(west, park.lng)
            east = max(east, park.lng)
        }
        return MKCoordinateRegion(
            center: CLLocationCoordinate2D(latitude: (south + north) / 2, longitude: (west + east) / 2),
            span: MKCoordinateSpan(
                latitudeDelta: min(max((north - south) * 1.4, 0.05), 170),
                longitudeDelta: min(max((east - west) * 1.4, 0.05), 360)
            )
        )
    }
}

/// A map viewport. `west` is greater than `east` when it crosses the antimeridian.
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
        // Crossing viewports are rare, so refetching for them is fine.
        guard !crossesAntimeridian, !other.crossesAntimeridian else { return false }
        return west <= other.west && east >= other.east
    }
}
