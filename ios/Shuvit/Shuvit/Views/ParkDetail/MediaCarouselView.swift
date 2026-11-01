import AVKit
import SwiftUI

struct MediaCarouselView: View {
    let media: [MediaItem]
    @State var currentIndex: Int
    var onUserBlocked: () -> Void = {}

    @Environment(\.dismiss) private var dismiss
    @State private var showingContributorProfile = false
    @State private var selectedContributorId: UUID?
    @State private var showingLogin = false
    @State private var confirmingReport = false
    @State private var confirmingBlock = false
    @State private var notice: String?

    private var current: MediaItem? {
        media.indices.contains(currentIndex) ? media[currentIndex] : nil
    }

    private var isOwnMedia: Bool {
        current?.userId == AuthManager.shared.currentUser?.id
    }

    var body: some View {
        NavigationStack {
            ZStack {
                Color.black.ignoresSafeArea()

                TabView(selection: $currentIndex) {
                    ForEach(Array(media.enumerated()), id: \.element.id) { index, item in
                        VStack(spacing: 0) {
                            Spacer()

                            if item.mediaType == "video", let url = item.fullFileURL {
                                InlineVideoPlayer(url: url, isActive: index == currentIndex)
                                    .aspectRatio(16 / 9, contentMode: .fit)
                            } else {
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
                            }

                            Spacer()

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
                ToolbarItem(placement: .primaryAction) {
                    if !isOwnMedia {
                        Menu {
                            Button("Report", systemImage: "flag") {
                                requireSignIn { confirmingReport = true }
                            }
                            Button("Block User", systemImage: "hand.raised", role: .destructive) {
                                requireSignIn { confirmingBlock = true }
                            }
                        } label: {
                            Image(systemName: "ellipsis.circle")
                                .foregroundStyle(.white)
                        }
                    }
                }
            }
            .toolbarBackground(.hidden, for: .navigationBar)
            .sheet(isPresented: $showingContributorProfile) {
                if let userId = selectedContributorId {
                    ContributorProfileView(userId: userId)
                }
            }
            .sheet(isPresented: $showingLogin) {
                LoginView()
            }
            .confirmationDialog("Why are you reporting this?", isPresented: $confirmingReport, titleVisibility: .visible) {
                ForEach(["Inappropriate or offensive", "Spam", "Not this skatepark", "Someone else's content"], id: \.self) { reason in
                    Button(reason) {
                        Task { await report(reason: reason) }
                    }
                }
            }
            .alert("Block this user?", isPresented: $confirmingBlock) {
                Button("Block", role: .destructive) {
                    Task { await blockCurrentUser() }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("You won't see their photos and videos anymore.")
            }
            .alert(notice ?? "", isPresented: Binding(get: { notice != nil }, set: { if !$0 { notice = nil } })) {
                Button("OK") {}
            }
        }
    }

    private func requireSignIn(then action: () -> Void) {
        if AuthManager.shared.isAuthenticated {
            action()
        } else {
            showingLogin = true
        }
    }

    private func report(reason: String) async {
        guard let current else { return }
        do {
            try await APIClient.shared.send(.reportMedia(id: current.id, reason: reason))
            notice = "Thanks. We'll review this within 48 hours."
        } catch {
            notice = error.localizedDescription
        }
    }

    private func blockCurrentUser() async {
        guard let current else { return }
        do {
            try await APIClient.shared.send(.blockUser(id: current.userId))
            onUserBlocked()
            dismiss()
        } catch {
            notice = error.localizedDescription
        }
    }
}

private struct InlineVideoPlayer: View {
    let isActive: Bool
    @State private var player: AVPlayer

    init(url: URL, isActive: Bool) {
        self.isActive = isActive
        self._player = State(initialValue: AVPlayer(url: url))
    }

    var body: some View {
        VideoPlayer(player: player)
            .onChange(of: isActive) { _, active in
                if !active { player.pause() }
            }
            .onDisappear { player.pause() }
    }
}
