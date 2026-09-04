from pathlib import Path

path = Path("src/android/app/src/main/java/org/yuzu/yuzu_emu/ui/GamesFragment.kt")
text = path.read_text()
old = '''    private fun updateLibraryHeroFromScroll() {
        if (_binding == null || displayedGames.isEmpty()) return
        val recycler = binding.gridGames as? RecyclerView ?: return
        val position = when (val lm = recycler.layoutManager) {
            is GridLayoutManager -> lm.findFirstVisibleItemPosition()
            is LinearLayoutManager -> if (getCurrentViewType() == GameAdapter.VIEW_TYPE_CAROUSEL)
                (recycler as? CarouselRecyclerView)?.getClosestChildPosition() ?: lm.findFirstVisibleItemPosition()
            else lm.findFirstVisibleItemPosition()
            else -> RecyclerView.NO_POSITION
        }
        if (position in displayedGames.indices) showLibraryHero(displayedGames[position])
    }
'''
new = '''    private fun updateLibraryHeroFromScroll() {
        if (_binding == null || displayedGames.isEmpty()) return
        val recycler = binding.gridGames as? RecyclerView ?: return
        val position = when (val lm = recycler.layoutManager) {
            is GridLayoutManager -> lm.findFirstVisibleItemPosition()
            is LinearLayoutManager -> {
                if (getCurrentViewType() == GameAdapter.VIEW_TYPE_CAROUSEL) {
                    (recycler as? CarouselRecyclerView)?.getClosestChildPosition()
                        ?: lm.findFirstVisibleItemPosition()
                } else {
                    lm.findFirstVisibleItemPosition()
                }
            }
            else -> RecyclerView.NO_POSITION
        }
        if (position in displayedGames.indices) {
            showLibraryHero(displayedGames[position])
        }
    }
'''
if old not in text:
    raise SystemExit("Expected malformed Home Frontend scroll block not found")
path.write_text(text.replace(old, new, 1))
print("Fixed Home Frontend hero scroll selector")
