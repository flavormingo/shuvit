import SwiftUI

@main
struct ShuvitApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .onOpenURL { url in
                    _ = AuthManager.shared.handleDeepLink(url: url)
                }
                .task {
                    if AuthManager.shared.isAuthenticated {
                        await AuthManager.shared.fetchUser()
                    }
                }
        }
    }
}

struct ContentView: View {
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            ParkMapView()
                .tabItem {
                    Label("Map", systemImage: "map")
                }
                .tag(0)

            FavoritesListView()
                .tabItem {
                    Label("Favorites", systemImage: "heart")
                }
                .tag(1)

            ProfileView()
                .tabItem {
                    Label("Profile", systemImage: "person")
                }
                .tag(2)
        }
        .tint(.primary)
    }
}

#Preview {
    ContentView()
}
