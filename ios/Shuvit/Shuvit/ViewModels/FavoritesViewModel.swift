import Foundation
import Observation

@Observable
@MainActor
final class FavoritesViewModel {
    var favorites: [Favorite] = []
    var isLoading = false
    var errorMessage: String?

    func load() async {
        guard AuthManager.shared.isAuthenticated else { return }
        isLoading = true
        errorMessage = nil

        do {
            let results: [Favorite] = try await APIClient.shared.request(.favorites)
            favorites = results
        } catch {
            errorMessage = error.localizedDescription
        }

        isLoading = false
    }

    func removeFavorite(parkId: UUID) async {
        do {
            try await APIClient.shared.send(.removeFavorite(parkId: parkId))
            favorites.removeAll { $0.parkId == parkId }
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
