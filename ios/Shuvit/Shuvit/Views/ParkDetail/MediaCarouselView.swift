import SwiftUI

struct MediaCarouselView: View {
    let media: [MediaItem]
    @State var currentIndex: Int
    @Environment(\.dismiss) private var dismiss
    @State private var showingContributorProfile = false
    @State private var selectedContributorId: UUID?

    var body: some View {
        NavigationStack {
            ZStack {
                Color.black.ignoresSafeArea()

                TabView(selection: $currentIndex) {
                    ForEach(Array(media.enumerated()), id: \.element.id) { index, item in
                        VStack(spacing: 0) {
                            Spacer()

                            AsyncImage(url: item.fullFileURL) { phase in
                                switch phase {
                                case .success(let image):
                                    image
                                        .resizable()
                                        .aspectRatio(contentMode: .fit)
                                case .failure:
                                    Image(systemName: "photo")
                                        .font(.largeTitle)
                                        .foregroundStyle(.gray)
                                case .empty:
                                    ProgressView()
                                        .tint(.white)
                                @unknown default:
                                    EmptyView()
                                }
                            }

                            Spacer()

                            // Info bar
                            VStack(spacing: 12) {
                                if let desc = item.description, !desc.isEmpty {
                                    Text(desc)
                                        .font(.subheadline)
                                        .foregroundStyle(.white)
                                }

                                if let name = item.contributorName {
                                    Button {
                                        selectedContributorId = item.userId
                                        showingContributorProfile = true
                                    } label: {
                                        Text("Contributed by \(name)")
                                            .font(.caption)
                                            .foregroundStyle(.white.opacity(0.7))
                                            .underline()
                                            .padding(.vertical, 8)
                                    }
                                }
                            }
                            .padding(.bottom, 48)
                        }
                        .tag(index)
                    }
                }
                .tabViewStyle(.page(indexDisplayMode: .automatic))

                // Counter
                VStack {
                    HStack {
                        Spacer()
                        Text("\(currentIndex + 1) / \(media.count)")
                            .font(.caption.weight(.medium))
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .background(.ultraThinMaterial, in: Capsule())
                    }
                    .padding(.horizontal, 20)
                    .padding(.top, 8)
                    Spacer()
                }
            }
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Close") {
                        dismiss()
                    }
                    .foregroundStyle(.white)
                }
            }
            .toolbarBackground(.hidden, for: .navigationBar)
            .sheet(isPresented: $showingContributorProfile) {
                if let userId = selectedContributorId {
                    ContributorProfileView(userId: userId)
                }
            }
        }
    }
}
