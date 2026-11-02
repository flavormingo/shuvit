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
    @State private var filters = ParkFilters()
    @State private var currentRegion: MKCoordinateRegion?
    @State private var hasSetInitialCamera = false
    @State private var hasCenteredOnUser = false
    @FocusState private var searchFocused: Bool

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

                ForEach(viewModel.parks) { park in
                    Annotation(park.name, coordinate: park.coordinate) {
                        ParkAnnotationView(park: park, isSelected: selectedPark?.id == park.id)
                            .accessibilityIdentifier("park-pin")
                    }
                    .tag(park)
                }

                ForEach(viewModel.clusters) { cluster in
                    Annotation("", coordinate: cluster.coordinate) {
                        Button {
                            zoom(into: cluster)
                        } label: {
                            ClusterAnnotationView(count: cluster.count)
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("park-cluster")
                        .accessibilityLabel("\(cluster.count) skateparks. Zoom in.")
                    }
                    .annotationTitles(.hidden)
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
                viewModel.load(region: context.region, filters: filters)
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
            guard !hasCenteredOnUser, let location = locationManager.location else { return }
            hasCenteredOnUser = true
            moveCamera(to: location)
        }
        .onChange(of: filters) {
            if let currentRegion {
                viewModel.load(region: currentRegion, filters: filters)
            }
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

    private func zoom(into cluster: ParkCluster) {
        let currentSpan = currentRegion?.span.longitudeDelta ?? 360
        let fit = max(cluster.north - cluster.south, cluster.east - cluster.west) * 1.6
        let span = max(min(fit, currentSpan / 2), 0.002)
        withAnimation {
            cameraPosition = .region(MKCoordinateRegion(
                center: CLLocationCoordinate2D(
                    latitude: (cluster.south + cluster.north) / 2,
                    longitude: (cluster.west + cluster.east) / 2
                ),
                span: MKCoordinateSpan(latitudeDelta: span, longitudeDelta: span)
            ))
        }
    }

    private func show(_ park: Skatepark) {
        hasCenteredOnUser = true
        selectedPark = park
        finishSearch()
        withAnimation {
            cameraPosition = .region(MKCoordinateRegion(
                center: park.coordinate,
                latitudinalMeters: 1500,
                longitudinalMeters: 1500
            ))
        }
    }

    private func show(_ place: PlaceResult) {
        hasCenteredOnUser = true
        selectedPark = nil
        finishSearch()
        withAnimation {
            cameraPosition = .region(place.region)
        }
    }

    private func finishSearch() {
        searchFocused = false
        viewModel.clearSearch()
    }

    private var searchResults: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 0) {
                if viewModel.parkResults.isEmpty && viewModel.placeResults.isEmpty {
                    Text("No parks or places found")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .padding(16)
                }

                if !viewModel.placeResults.isEmpty {
                    resultsHeader("Places")
                    ForEach(viewModel.placeResults) { place in
                        resultRow(icon: "mappin.circle.fill", title: place.name, subtitle: place.subtitle) {
                            show(place)
                        }
                    }
                }

                if !viewModel.parkResults.isEmpty {
                    resultsHeader("Parks")
                    ForEach(viewModel.parkResults) { park in
                        resultRow(icon: "figure.skateboarding", title: park.name, subtitle: park.locationString) {
                            show(park)
                        }
                    }
                }
            }
        }
        .frame(maxHeight: 320)
        .accessibilityIdentifier("search-results")
    }

    private func resultsHeader(_ title: String) -> some View {
        Text(title.uppercased())
            .font(.system(size: 11, weight: .semibold))
            .foregroundStyle(.tertiary)
            .kerning(0.8)
            .padding(.horizontal, 16)
            .padding(.top, 12)
            .padding(.bottom, 4)
    }

    private func resultRow(icon: String, title: String, subtitle: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: icon)
                    .foregroundStyle(.secondary)
                    .frame(width: 22)

                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.subheadline.weight(.semibold))
                        .lineLimit(1)
                    if !subtitle.isEmpty {
                        Text(subtitle)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                }

                Spacer()
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private var searchBar: some View {
        VStack(spacing: 0) {
            if viewModel.hasSearched {
                searchResults

                Rectangle()
                    .fill(Color.primary.opacity(0.08))
                    .frame(height: 1)
            }

            HStack(spacing: 12) {
                Image(systemName: "magnifyingglass")
                    .font(.body.weight(.medium))
                    .foregroundStyle(.secondary)

                TextField("Find a park or place", text: $searchText)
                    .textFieldStyle(.plain)
                    .font(.body)
                    .focused($searchFocused)
                    .onSubmit {
                        let query = searchText.trimmingCharacters(in: .whitespaces)
                        guard !query.isEmpty else { return }
                        Task { await viewModel.search(query: query) }
                    }

                if viewModel.isSearching {
                    ProgressView()
                } else if !searchText.isEmpty {
                    Button {
                        searchText = ""
                        finishSearch()
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
                            .foregroundStyle(showFilters || filters.activeCount > 0 ? Color(.systemBackground) : .secondary)
                            .frame(width: 36, height: 36)
                            .background(
                                showFilters || filters.activeCount > 0 ? Color.primary : Color(.systemGray5),
                                in: RoundedRectangle(cornerRadius: 10)
                            )

                        if filters.activeCount > 0 && !showFilters {
                            Text("\(filters.activeCount)")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundStyle(.white)
                                .frame(width: 16, height: 16)
                                .background(Color.accentColor, in: Circle())
                                .offset(x: 4, y: -4)
                        }
                    }
                }
                .accessibilityIdentifier("filter-toggle")
                .accessibilityLabel("Filters")
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
                        filterRow(title: "Setting", options: ["Indoor", "Outdoor", "Both"], selection: $filters.environment)
                        filterRow(title: "Price", options: ["Free", "Paid"], selection: $filters.price)

                        if filters.activeCount > 0 {
                            Button {
                                withAnimation(.easeInOut(duration: 0.2)) {
                                    filters = ParkFilters()
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

struct ClusterAnnotationView: View {
    let count: Int

    private var diameter: CGFloat {
        switch count {
        case ..<10: return 34
        case ..<100: return 40
        case ..<1000: return 48
        default: return 56
        }
    }

    private var label: String {
        count < 1000 ? "\(count)" : String(format: "%.1fk", Double(count) / 1000)
    }

    var body: some View {
        Text(label)
            .font(.system(size: 13, weight: .bold, design: .rounded))
            .foregroundStyle(.white)
            .frame(width: diameter, height: diameter)
            .background(Color.black, in: Circle())
            .overlay(Circle().stroke(.white.opacity(0.9), lineWidth: 2))
            .shadow(color: .black.opacity(0.3), radius: 4, y: 2)
            .contentShape(Circle())
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
