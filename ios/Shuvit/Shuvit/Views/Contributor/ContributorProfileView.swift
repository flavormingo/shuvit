import SwiftUI

struct ContributorProfileView: View {
    let userId: UUID
    @Environment(\.dismiss) private var dismiss
    @State private var profile: UserProfile?
    @State private var contributions: [Contribution] = []
    @State private var isLoading = true

    private let columns = [
        GridItem(.flexible(), spacing: 4),
        GridItem(.flexible(), spacing: 4),
        GridItem(.flexible(), spacing: 4),
    ]

    var body: some View {
        NavigationStack {
            ScrollView {
                if isLoading {
                    ProgressView()
                        .padding(.top, 60)
                } else if let profile {
                    VStack(spacing: 24) {
                        VStack(spacing: 12) {
                            AsyncImage(url: profile.avatarFullURL) { phase in
                                switch phase {
                                case .success(let image):
                                    image
                                        .resizable()
                                        .aspectRatio(contentMode: .fill)
                                        .frame(width: 80, height: 80)
                                        .clipShape(Circle())
                                default:
                                    Image(systemName: "person.circle.fill")
                                        .font(.system(size: 64))
                                        .foregroundStyle(.secondary)
                                }
                            }

                            Text(profile.displayName ?? "Skater")
                                .font(.title2.weight(.bold))
                                .lineLimit(1)

                            RankBadge(rank: profile.rank)
                        }
                        .padding(.top, 20)

                        HStack(spacing: 32) {
                            statItem(value: "\(profile.approvedCount)", label: "Contributions")
                            statItem(value: "\(profile.parksCount)", label: "Parks")
                        }

                        if contributions.isEmpty {
                            Text("No contributions yet")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                                .padding(.top, 20)
                        } else {
                            VStack(alignment: .leading, spacing: 12) {
                                Text("Contributions")
                                    .font(.headline)
                                    .padding(.horizontal, 16)

                                LazyVGrid(columns: columns, spacing: 4) {
                                    ForEach(contributions) { item in
                                        AsyncImage(url: item.fullThumbnailURL) { phase in
                                            switch phase {
                                            case .success(let image):
                                                image
                                                    .resizable()
                                                    .aspectRatio(1, contentMode: .fill)
                                                    .clipped()
                                            default:
                                                Rectangle()
                                                    .fill(Color(.systemGray5))
                                                    .aspectRatio(1, contentMode: .fill)
                                            }
                                        }
                                    }
                                }
                                .padding(.horizontal, 16)
                            }
                        }
                    }
                }
            }
            .navigationTitle("Profile")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") { dismiss() }
                }
            }
            .task { await load() }
        }
    }

    private func statItem(value: String, label: String) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.title3.weight(.bold))
            Text(label)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    private func load() async {
        isLoading = true
        async let profileReq: UserProfile? = try? APIClient.shared.request(.userProfile(id: userId))
        async let contribReq: [Contribution] = (try? APIClient.shared.request(.userContributions(id: userId))) ?? []

        profile = await profileReq
        contributions = await contribReq
        isLoading = false
    }
}

struct RankBadge: View {
    let rank: String

    private var color: Color {
        switch rank {
        case "Legend": return .yellow
        case "Wizard": return .purple
        case "Pro": return .blue
        default: return .gray
        }
    }

    private var icon: String {
        switch rank {
        case "Legend": return "crown.fill"
        case "Wizard": return "wand.and.stars"
        case "Pro": return "star.fill"
        default: return "figure.skateboarding"
        }
    }

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
            Text(rank)
        }
        .font(.caption.weight(.semibold))
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(color.opacity(0.15), in: Capsule())
        .foregroundStyle(color)
    }
}
