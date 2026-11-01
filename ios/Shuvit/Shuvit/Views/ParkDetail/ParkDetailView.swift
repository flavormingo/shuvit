import SwiftUI
import MapKit

struct ParkDetailView: View {
    let parkId: UUID
    let parkName: String

    @State private var viewModel: ParkDetailViewModel
    @State private var showingLogin = false
    @State private var showingMediaSubmit = false
    @State private var activeTooltip: String?

    init(parkId: UUID, parkName: String) {
        self.parkId = parkId
        self.parkName = parkName
        self._viewModel = State(initialValue: ParkDetailViewModel(parkId: parkId))
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                // Hero / Map header
                mapHeader

                VStack(alignment: .leading, spacing: 20) {
                    // Title + actions
                    titleSection

                    // Info chips
                    if let park = viewModel.park {
                        infoSection(park)
                    }

                    // Features
                    if let park = viewModel.park {
                        featuresSection(park)
                    }

                    // Hours
                    if let park = viewModel.park {
                        hoursSection(park)
                    }

                    // Description
                    if let desc = viewModel.park?.description, !desc.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("About")
                                .font(.headline)
                            Text(desc)
                                .font(.body)
                                .foregroundStyle(.secondary)
                        }
                    }

                    // Address
                    if let address = viewModel.park?.address, !address.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Address")
                                .font(.headline)
                            Label(address, systemImage: "mappin.circle.fill")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                    }

                    // Media Gallery
                    if let media = viewModel.park?.media, !media.isEmpty {
                        mediaSection(media)
                    }

                    // Submit media button
                    Button {
                        if AuthManager.shared.isAuthenticated {
                            showingMediaSubmit = true
                        } else {
                            showingLogin = true
                        }
                    } label: {
                        Label("Add Photo or Video", systemImage: "camera.fill")
                            .font(.subheadline.weight(.semibold))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(Color(.systemGray6), in: RoundedRectangle(cornerRadius: 10))
                    }
                }
                .padding(20)
            }
        }
        .navigationTitle(parkName)
        .navigationBarTitleDisplayMode(.inline)
        .presentationDragIndicator(.visible)
        .task { await viewModel.load() }
        .overlay {
            if viewModel.isLoading && viewModel.park == nil {
                ProgressView()
            }
        }
        .sheet(isPresented: $showingLogin) {
            LoginView()
        }
        .sheet(isPresented: $showingMediaSubmit) {
            SubmitMediaSheet(parkId: parkId)
        }
    }

    private var mapHeader: some View {
        Map {
            if let park = viewModel.park {
                Marker(park.name, coordinate: park.coordinate)
                    .tint(.black)
            }
        }
        .frame(height: 200)
        .allowsHitTesting(true)
        .onTapGesture {
            guard let park = viewModel.park else { return }
            let mapItem = MKMapItem(placemark: MKPlacemark(coordinate: park.coordinate))
            mapItem.name = park.name
            mapItem.openInMaps(launchOptions: [MKLaunchOptionsDirectionsModeKey: MKLaunchOptionsDirectionsModeDriving])
        }
    }

    private var titleSection: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 4) {
                Text(parkName)
                    .font(.title2.weight(.bold))

                if let park = viewModel.park {
                    Text(park.locationString)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            Button {
                if AuthManager.shared.isAuthenticated {
                    Task { await viewModel.toggleFavorite() }
                } else {
                    showingLogin = true
                }
            } label: {
                Image(systemName: viewModel.isFavorited ? "heart.fill" : "heart")
                    .font(.title2)
                    .foregroundStyle(viewModel.isFavorited ? .red : .secondary)
                    .contentTransition(.symbolEffect(.replace))
            }
        }
    }

    private func infoSection(_ park: SkateparkDetail) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 10) {
                if let env = park.environment {
                    infoPill(
                        icon: "cloud.sun.fill",
                        text: env.capitalized,
                        tooltip: "Indoor, outdoor, or both"
                    )
                }
                if let type = park.parkType {
                    infoPill(icon: "figure.skateboarding", text: type.capitalized, tooltip: "Park style: street, transition, mixed, or DIY")
                }
                if let surface = park.surface {
                    infoPill(icon: "square.3.layers.3d.top.filled", text: surface.capitalized, tooltip: "Riding surface material")
                }
                if park.lighting == true {
                    infoPill(icon: "lightbulb.fill", text: "Lit", tooltip: "This park has lights for night sessions")
                }
                if park.isFree {
                    infoPill(icon: "checkmark.circle.fill", text: "Free", tooltip: "No entry fee required")
                }
                if let rating = park.rating {
                    infoPill(icon: "star.fill", text: String(format: "%.1f", rating), tooltip: "Community rating out of 5.0")
                }
                if let difficulty = park.difficulty {
                    infoPill(icon: "gauge.medium", text: difficulty.capitalized, tooltip: "Skill level: beginner, intermediate, or advanced")
                }
            }
        }
    }

    private func infoPill(icon: String, text: String, tooltip: String) -> some View {
        ParkPill(icon: icon, text: text)
            .popover(isPresented: tooltipBinding(for: tooltip)) {
                Text(tooltip)
                    .font(.footnote)
                    .padding(12)
                    .presentationCompactAdaptation(.popover)
            }
            .onTapGesture {
                activeTooltip = tooltip
            }
    }

    private func tooltipBinding(for tooltip: String) -> Binding<Bool> {
        Binding(
            get: { activeTooltip == tooltip },
            set: { if !$0 { activeTooltip = nil } }
        )
    }

    @ViewBuilder
    private func featuresSection(_ park: SkateparkDetail) -> some View {
        if let features = park.features, !features.isEmpty {
            let displayable = features.filter { $0.key != "indoor_outdoor" }
            if !displayable.isEmpty {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Features")
                        .font(.headline)
                    FlowLayout(spacing: 6) {
                        ForEach(displayable.sorted(by: { $0.key < $1.key }), id: \.key) { key, value in
                            let label = if let str = value.value as? String, str != "true" && str != "yes" {
                                "\(key.replacingOccurrences(of: "_", with: " ").capitalized): \(str)"
                            } else {
                                key.replacingOccurrences(of: "_", with: " ").capitalized
                            }
                            ParkPill(icon: featureIcon(key), text: label)
                        }
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func hoursSection(_ park: SkateparkDetail) -> some View {
        if let hours = park.hours, !hours.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                Text("Hours")
                    .font(.headline)
                VStack(alignment: .leading, spacing: 4) {
                    ForEach(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"], id: \.self) { day in
                        if let value = hours[day] {
                            HStack {
                                Text(day.capitalized)
                                    .font(.subheadline)
                                    .frame(width: 100, alignment: .leading)
                                Text(String(describing: value.value))
                                    .font(.subheadline)
                                    .foregroundStyle(.secondary)
                            }
                        }
                    }
                }
            }
        }
    }

    private func featureIcon(_ key: String) -> String {
        switch key.lowercased() {
        case let k where k.contains("bowl"): return "circle.bottomhalf.filled"
        case let k where k.contains("rail"): return "line.diagonal"
        case let k where k.contains("ledge"): return "rectangle.fill"
        case let k where k.contains("ramp"): return "triangle.fill"
        case let k where k.contains("half"): return "semicircle.fill"
        case let k where k.contains("pool"): return "drop.fill"
        case let k where k.contains("stair"): return "stairs"
        default: return "star.fill"
        }
    }

    private func mediaSection(_ media: [MediaItem]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Photos & Videos")
                .font(.headline)

            ParkMediaGallery(media: media)
        }
    }
}

#Preview {
    NavigationStack {
        ParkDetailView(parkId: UUID(), parkName: "Lee & Joe Jamail Skatepark")
    }
}
