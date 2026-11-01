import SwiftUI

struct ContributionsView: View {
    @State private var contributions: [Contribution] = []
    @State private var isLoading = true

    var body: some View {
        Group {
            if isLoading {
                ProgressView()
            } else if contributions.isEmpty {
                VStack(spacing: 16) {
                    Image(systemName: "camera")
                        .font(.system(size: 48))
                        .foregroundStyle(.secondary)

                    Text("No contributions yet")
                        .font(.headline)

                    Text("Submit photos and videos to skateparks\nto see them here.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
            } else {
                List(contributions) { item in
                    NavigationLink {
                        ParkDetailView(parkId: item.parkId, parkName: item.parkName)
                    } label: {
                        HStack(spacing: 12) {
                            AsyncImage(url: item.fullThumbnailURL) { phase in
                                switch phase {
                                case .success(let image):
                                    image
                                        .resizable()
                                        .aspectRatio(contentMode: .fill)
                                        .frame(width: 56, height: 56)
                                        .clipShape(RoundedRectangle(cornerRadius: 8))
                                default:
                                    RoundedRectangle(cornerRadius: 8)
                                        .fill(Color(.systemGray5))
                                        .frame(width: 56, height: 56)
                                }
                            }

                            VStack(alignment: .leading, spacing: 4) {
                                Text(item.parkName)
                                    .font(.subheadline.weight(.semibold))
                                    .lineLimit(1)

                                if let desc = item.description, !desc.isEmpty {
                                    Text(desc)
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                        .lineLimit(1)
                                }

                                Text(item.mediaType.capitalized)
                                    .font(.caption2)
                                    .padding(.horizontal, 8)
                                    .padding(.vertical, 3)
                                    .background(Color(.systemGray6), in: Capsule())
                            }
                        }
                        .padding(.vertical, 4)
                    }
                }
                .listStyle(.plain)
            }
        }
        .navigationTitle("Contributions")
        .task { await load() }
    }

    private func load() async {
        isLoading = true
        contributions = (try? await APIClient.shared.request(.myContributions)) ?? []
        isLoading = false
    }
}
