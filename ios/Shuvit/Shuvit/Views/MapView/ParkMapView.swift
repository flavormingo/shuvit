import SwiftUI
import MapKit

struct ParkMapView: View {
    @State private var viewModel = MapViewModel()
    @State private var locationManager = LocationManager()
    @State private var selectedPark: SkateparkNear?
    @State private var showingDetail = false
    @State private var searchText = ""
    @State private var cameraPosition: MapCameraPosition = .userLocation(fallback: .automatic)
    @State private var showFilters = false
    @State private var filterType: String?
    @State private var filterEnvironment: String?
    @State private var filterPrice: String?
    @State private var currentRegion: MKCoordinateRegion?
    @State private var hasSetInitialCamera = false
    @State private var hasCenteredOnUser = false
    @FocusState private var searchFocused: Bool

    private var activeFilterCount: Int {
        [filterType, filterEnvironment, filterPrice].compactMap { $0 }.count
    }

    private var filteredParks: [SkateparkNear] {
        viewModel.parks.filter { park in
            if let type = filterType, park.parkType?.lowercased() != type { return false }
            if let env = filterEnvironment, park.environment?.lowercased() != env { return false }
            if let price = filterPrice {
                if price == "free" && !park.isFree { return false }
                if price == "paid" && park.isFree { return false }
            }
            return true
        }
    }

    private let fallbackCenter = CLLocationCoordinate2D(latitude: 29.7604, longitude: -95.3698)

    private func distanceKm(to park: Skatepark) -> Double? {
        guard let user = locationManager.location else { return nil }
        return CLLocation(latitude: user.latitude, longitude: user.longitude)
            .distance(from: CLLocation(latitude: park.lat, longitude: park.lng)) / 1000
    }

    var body: some View {
        ZStack(alignment: .top) {
            Map(position: $cameraPosition, selection: $selectedPark) {
                UserAnnotation()

                ForEach(filteredParks) { park in
                    Annotation(park.name, coordinate: park.coordinate) {
                        ParkAnnotationView(park: park, isSelected: selectedPark?.id == park.id)
                    }
                    .tag(park)
                }
            }
            .mapStyle(.standard(elevation: .flat))
            .mapControls {
                MapUserLocationButton()
                MapCompass()
                MapScaleView()
            }
            .onMapCameraChange(frequency: .onEnd) { context in
                currentRegion = context.region
                viewModel.loadVisible(region: context.region)
            }

            VStack(spacing: 0) {
                Spacer()

                if let message = viewModel.errorMessage {
                    Text(message)
                        .font(.caption.weight(.medium))
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(.ultraThickMaterial, in: Capsule())
                        .padding(.bottom, 8)
                }

                if let park = selectedPark {
                    parkCard(park)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                }

                searchBar
            }
        }
        .sheet(isPresented: $showingDetail) {
            if let park = selectedPark {
                NavigationStack {
                    ParkDetailView(parkId: park.id, parkName: park.name)
                }
            }
        }
        .onAppear {
            guard !hasSetInitialCamera else { return }
            hasSetInitialCamera = true
            locationManager.requestPermission()
            if let location = locationManager.location { hasCenteredOnUser = true; moveCamera(to: location) }
            else { moveCamera(to: fallbackCenter) }
        }
        .onChange(of: locationManager.location?.latitude) {
            guard !hasCenteredOnUser, !viewModel.isShowingSearchResults,
                  let location = locationManager.location else { return }
            hasCenteredOnUser = true
            moveCamera(to: location)
        }
        .animation(.easeInOut(duration: 0.3), value: selectedPark)
    }

    private func moveCamera(to center: CLLocationCoordinate2D) {
        cameraPosition = .region(MKCoordinateRegion(
            center: center,
            latitudinalMeters: 30000,
            longitudinalMeters: 30000
        ))
    }

    private var searchBar: some View {
        VStack(spacing: 0) {
            HStack(spacing: 12) {
                Image(systemName: "magnifyingglass")
                    .font(.body.weight(.medium))
                    .foregroundStyle(.secondary)

                TextField("Find a skatepark", text: $searchText)
                    .textFieldStyle(.plain)
                    .font(.body)
                    .focused($searchFocused)
                    .onSubmit {
                        let query = searchText.trimmingCharacters(in: .whitespaces)
                        guard !query.isEmpty else { return }
                        Task {
                            if let region = await viewModel.search(query: query) {
                                withAnimation {
                                    cameraPosition = .region(region)
                                }
                            }
                        }
                    }

                if !searchText.isEmpty {
                    Button {
                        searchText = ""
                        selectedPark = nil
                        viewModel.clearSearch(region: currentRegion)
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .font(.body)
                            .foregroundStyle(.quaternary)
                    }
                }

                Button {
                    withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                        showFilters.toggle()
                        searchFocused = false
                    }
                } label: {
                    ZStack(alignment: .topTrailing) {
                        Image(systemName: "slider.horizontal.3")
                            .font(.body.weight(.medium))
                            .foregroundStyle(showFilters || activeFilterCount > 0 ? Color(.systemBackground) : .secondary)
                            .frame(width: 36, height: 36)
                            .background(
                                showFilters || activeFilterCount > 0 ? Color.primary : Color(.systemGray5),
                                in: RoundedRectangle(cornerRadius: 10)
                            )

                        if activeFilterCount > 0 && !showFilters {
                            Text("\(activeFilterCount)")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundStyle(.white)
                                .frame(width: 16, height: 16)
                                .background(Color.accentColor, in: Circle())
                                .offset(x: 4, y: -4)
                        }
                    }
                }
            }
            .padding(.leading, 16)
            .padding(.trailing, 10)
            .padding(.vertical, 12)

            if showFilters {
                VStack(spacing: 0) {
                    Rectangle()
                        .fill(Color.primary.opacity(0.08))
                        .frame(height: 1)

                    VStack(alignment: .leading, spacing: 14) {
                        filterRow(title: "Setting", options: ["Indoor", "Outdoor", "Both"], selection: $filterEnvironment)
                        filterRow(title: "Type", options: ["Street", "Transition", "Mixed", "DIY"], selection: $filterType)
                        filterRow(title: "Price", options: ["Free", "Paid"], selection: $filterPrice)

                        if activeFilterCount > 0 {
                            Button {
                                withAnimation(.easeInOut(duration: 0.2)) {
                                    filterType = nil
                                    filterEnvironment = nil
                                    filterPrice = nil
                                }
                            } label: {
                                Text("Clear all")
                                    .font(.caption.weight(.semibold))
                                    .foregroundStyle(.secondary)
                            }
                            .frame(maxWidth: .infinity, alignment: .trailing)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 14)
                }
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(.ultraThickMaterial, in: RoundedRectangle(cornerRadius: 16))
        .shadow(color: .black.opacity(0.08), radius: 20, y: 8)
        .padding(.horizontal, 16)
        .padding(.bottom, 8)
    }

    private func filterRow(title: String, options: [String], selection: Binding<String?>) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title.uppercased())
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(.tertiary)
                .kerning(0.8)

            HStack(spacing: 6) {
                ForEach(options, id: \.self) { option in
                    let isActive = selection.wrappedValue == option.lowercased()
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            selection.wrappedValue = isActive ? nil : option.lowercased()
                        }
                    } label: {
                        Text(option)
                            .font(.caption.weight(.semibold))
                            .padding(.horizontal, 14)
                            .padding(.vertical, 7)
                            .background(
                                isActive ? Color.primary : Color.primary.opacity(0.06),
                                in: Capsule()
                            )
                            .foregroundStyle(isActive ? Color(.systemBackground) : .primary)
                    }
                }
            }
        }
    }

    private func parkCard(_ park: SkateparkNear) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            if let distance = distanceKm(to: park) {
                Text(UserSettings.shared.formatDistance(km: distance))
                    .font(.caption.weight(.medium))
                    .foregroundStyle(Color(.systemBackground))
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.primary, in: Capsule())
            }

            VStack(alignment: .leading, spacing: 4) {
                Text(park.name)
                    .font(.headline)
                    .lineLimit(1)

                Text(park.locationString)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    if let env = park.environment {
                        ParkPill(icon: "cloud.sun.fill", text: env.capitalized, inverted: true)
                    }
                    if let type = park.parkType {
                        ParkPill(icon: "figure.skateboarding", text: type.capitalized, inverted: true)
                    }
                    if park.isFree {
                        ParkPill(icon: "checkmark.circle.fill", text: "Free", inverted: true)
                    }
                    if let rating = park.rating {
                        ParkPill(icon: "star.fill", text: String(format: "%.1f", rating), inverted: true)
                    }
                    if let difficulty = park.difficulty {
                        ParkPill(icon: "gauge.medium", text: difficulty.capitalized, inverted: true)
                    }
                }
            }

            HStack(spacing: 10) {
                Button {
                    showingDetail = true
                } label: {
                    Text("Details")
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .background(Color.primary, in: RoundedRectangle(cornerRadius: 10))
                        .foregroundStyle(Color(.systemBackground))
                }

                Button {
                    let coordinate = park.coordinate
                    let mapItem = MKMapItem(placemark: MKPlacemark(coordinate: coordinate))
                    mapItem.name = park.name
                    mapItem.openInMaps(launchOptions: [MKLaunchOptionsDirectionsModeKey: MKLaunchOptionsDirectionsModeDriving])
                } label: {
                    Text("Directions")
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                        .background(Color(.systemGray5), in: RoundedRectangle(cornerRadius: 10))
                        .foregroundStyle(.primary)
                }
            }
        }
        .padding(16)
        .background(.ultraThickMaterial, in: RoundedRectangle(cornerRadius: 16))
        .padding(.horizontal, 16)
        .padding(.bottom, 16)
    }

}

struct ParkAnnotationView: View {
    let park: SkateparkNear
    let isSelected: Bool

    var body: some View {
        ZStack {
            Circle()
                .fill(isSelected ? Color.accentColor : Color.black)
                .frame(width: isSelected ? 36 : 28, height: isSelected ? 36 : 28)
                .shadow(color: .black.opacity(0.3), radius: 4, y: 2)

            Image(systemName: "skateboard")
                .font(.system(size: isSelected ? 16 : 12))
                .foregroundStyle(.white)
        }
        .animation(.spring(response: 0.3), value: isSelected)
    }
}

#Preview {
    ParkMapView()
}
