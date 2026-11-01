import CoreLocation
import Observation

@Observable
@MainActor
final class MapViewModel {
    var parks: [SkateparkNear] = []
    var isLoading = false
    var errorMessage: String?
    var searchQuery = ""

    private var lastFetchCenter: CLLocationCoordinate2D?
    private var fetchTask: Task<Void, Never>?

    func loadNearby(center: CLLocationCoordinate2D, radiusKm: Double = 50) {
        // Debounce: skip if center hasn't moved significantly
        if let last = lastFetchCenter {
            let latDiff = abs(last.latitude - center.latitude)
            let lngDiff = abs(last.longitude - center.longitude)
            if latDiff < 0.01 && lngDiff < 0.01 {
                return
            }
        }

        lastFetchCenter = center
        fetchTask?.cancel()

        fetchTask = Task {
            try? await Task.sleep(for: .milliseconds(500))
            guard !Task.isCancelled else { return }
            await fetchParks(lat: center.latitude, lng: center.longitude, radiusKm: radiusKm)
        }
    }

    func fetchParks(lat: Double, lng: Double, radiusKm: Double = 50) async {
        isLoading = true
        errorMessage = nil

        do {
            let results: [SkateparkNear] = try await APIClient.shared.request(
                .parksNear(lat: lat, lng: lng, radiusKm: radiusKm)
            )
            parks = results
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    /// Search parks and return the center coordinate of results for camera repositioning.
    func search(query: String) async -> CLLocationCoordinate2D? {
        isLoading = true
        errorMessage = nil

        var center: CLLocationCoordinate2D?

        do {
            let results: [Skatepark] = try await APIClient.shared.request(
                .parks(q: query)
            )
            parks = results
            if let first = parks.first {
                center = first.coordinate
            }
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
        return center
    }
}
