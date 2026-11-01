import SwiftUI

struct ParkMediaGallery: View {
    let media: [MediaItem]
    var onUserBlocked: () -> Void = {}
    @State private var showingCarousel = false
    @State private var selectedIndex = 0

    private let columns = [
        GridItem(.flexible(), spacing: 4),
        GridItem(.flexible(), spacing: 4),
        GridItem(.flexible(), spacing: 4),
    ]

    var body: some View {
        LazyVGrid(columns: columns, spacing: 4) {
            ForEach(Array(media.enumerated()), id: \.element.id) { index, item in
                Button {
                    selectedIndex = index
                    showingCarousel = true
                } label: {
                    mediaCell(item)
                }
            }
        }
        .fullScreenCover(isPresented: $showingCarousel) {
            MediaCarouselView(media: media, currentIndex: selectedIndex, onUserBlocked: onUserBlocked)
        }
    }

    private func mediaCell(_ item: MediaItem) -> some View {
        ZStack(alignment: .bottomTrailing) {
            AsyncImage(url: item.fullThumbnailURL) { phase in
                switch phase {
                case .success(let image):
                    image
                        .resizable()
                        .aspectRatio(1, contentMode: .fill)
                        .clipped()
                case .failure:
                    placeholder
                case .empty:
                    placeholder
                        .overlay(ProgressView())
                @unknown default:
                    placeholder
                }
            }
            .frame(minHeight: 100)
            .clipShape(RoundedRectangle(cornerRadius: 6))

            if item.mediaType == "video" {
                Image(systemName: "play.circle.fill")
                    .font(.title3)
                    .foregroundStyle(.white)
                    .shadow(radius: 2)
                    .padding(6)
            }
        }
    }

    private var placeholder: some View {
        Rectangle()
            .fill(Color(.systemGray5))
            .aspectRatio(1, contentMode: .fill)
    }
}
