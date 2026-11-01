import Foundation
import Observation

@Observable
@MainActor
final class ParkDetailViewModel {
    var park: SkateparkDetail?
    var isFavorited = false
    var isLoading = false
    var errorMessage: String?

    private let parkId: UUID

    init(parkId: UUID) {
        self.parkId = parkId
    }

    func load() async {
        isLoading = true
        do {
            let detail: SkateparkDetail = try await APIClient.shared.request(
                .parkDetail(id: parkId)
            )
            park = detail
        } catch {
            errorMessage = error.localizedDescription
        }

        if AuthManager.shared.isAuthenticated {
            do {
                let favs: [Favorite] = try await APIClient.shared.request(.favorites)
                isFavorited = favs.contains { $0.parkId == parkId }
            } catch {
                isFavorited = false
            }
        }

        isLoading = false
    }

    func toggleFavorite() async {
        guard AuthManager.shared.isAuthenticated else { return }

        do {
            if isFavorited {
                try await APIClient.shared.send(.removeFavorite(parkId: parkId))
                isFavorited = false
            } else {
                try await APIClient.shared.send(.addFavorite(parkId: parkId))
                isFavorited = true
            }
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
