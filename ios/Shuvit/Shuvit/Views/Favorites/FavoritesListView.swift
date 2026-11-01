import SwiftUI

struct FavoritesListView: View {
    @State private var viewModel = FavoritesViewModel()
    @State private var showingLogin = false

    var body: some View {
        NavigationStack {
            Group {
                if !AuthManager.shared.isAuthenticated {
                    notSignedInView
                } else if viewModel.isLoading && viewModel.favorites.isEmpty {
                    ProgressView()
                } else if viewModel.favorites.isEmpty {
                    emptyView
                } else {
                    favoritesList
                }
            }
            .navigationTitle("Favorites")
            // Keyed on sign-in state so favorites load right after signing in.
            .task(id: AuthManager.shared.isAuthenticated) {
                await viewModel.load()
            }
            .refreshable {
                await viewModel.load()
            }
            .sheet(isPresented: $showingLogin) {
                LoginView()
            }
        }
    }

    private var notSignedInView: some View {
        VStack(spacing: 20) {
            Image(systemName: "heart.slash")
                .font(.system(size: 64))
                .foregroundStyle(.secondary)
                .frame(height: 70)

            Text("Sign in to save favorites")
                .font(.headline)

            Button("Sign In") {
                showingLogin = true
            }
            .buttonStyle(.borderedProminent)
            .tint(.black)
        }
    }

    private var emptyView: some View {
        VStack(spacing: 16) {
            Image(systemName: "heart")
                .font(.system(size: 64))
                .foregroundStyle(.secondary)

            Text("No favorites yet")
                .font(.headline)

            Text("Tap the heart on any park to save it here.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }

    private var favoritesList: some View {
        List {
            ForEach(viewModel.favorites) { fav in
                if let park = fav.park {
                    NavigationLink {
                        ParkDetailView(parkId: park.id, parkName: park.name)
                    } label: {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(park.name)
                                .font(.headline)
                                .lineLimit(1)

                            Text(park.locationString)
                                .font(.caption)
                                .foregroundStyle(.secondary)

                            ScrollView(.horizontal, showsIndicators: false) {
                                HStack(spacing: 6) {
                                    if let env = park.environment {
                                        ParkPill(
                                            icon: "cloud.sun.fill",
                                            text: env.capitalized
                                        )
                                    }
                                    if let type = park.parkType {
                                        ParkPill(icon: "figure.skateboarding", text: type.capitalized)
                                    }
                                    if park.isFree {
                                        ParkPill(icon: "checkmark.circle.fill", text: "Free")
                                    }
                                    if let rating = park.rating {
                                        ParkPill(icon: "star.fill", text: String(format: "%.1f", rating))
                                    }
                                    if let difficulty = park.difficulty {
                                        ParkPill(icon: "gauge.medium", text: difficulty.capitalized)
                                    }
                                }
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }
            }
            .onDelete { indexSet in
                for index in indexSet {
                    let fav = viewModel.favorites[index]
                    Task { await viewModel.removeFavorite(parkId: fav.parkId) }
                }
            }
        }
        .listStyle(.plain)
    }

}

#Preview {
    FavoritesListView()
}
