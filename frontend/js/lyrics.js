/**
 * Wave — Synced Lyrics Module
 * Fetches lyrics from LRCLIB and syncs line highlighting to audio playback time.
 */

const Lyrics = {
    syncedLines: [],
    activeIndex: -1,
    currentTrackId: null,

    async loadLyrics(track) {
        if (!track || !track.video_id) return;

        const overlay = document.getElementById('lyrics-overlay');
        const contentEl = document.getElementById('lyrics-content');
        const loadingEl = document.getElementById('lyrics-loading');
        const badgeEl = document.getElementById('lyrics-badge');

        // Update header
        document.getElementById('lyrics-track-name').textContent = track.track_name || track.title || 'Unknown';
        document.getElementById('lyrics-artist').textContent = track.artist || 'Unknown Artist';

        this.currentTrackId = track.video_id;
        this.syncedLines = [];
        this.activeIndex = -1;

        loadingEl.classList.remove('hidden');
        contentEl.innerHTML = '';

        try {
            const title = encodeURIComponent(track.track_name || track.title || '');
            const artist = encodeURIComponent(track.artist || '');
            const duration = track.duration || 0;
            const language = encodeURIComponent(track.language || '');

            const res = await API.get(`/api/lyrics/${track.video_id}?title=${title}&artist=${artist}&duration=${duration}&language=${language}`);
            loadingEl.classList.add('hidden');

            if (res && res.has_synced && res.synced && res.synced.length > 0) {
                this.syncedLines = res.synced;
                badgeEl.textContent = 'Synced Lyrics';
                badgeEl.style.display = 'inline-block';
                this.renderSynced();
            } else if (res && res.plain) {
                badgeEl.textContent = 'Plain Lyrics';
                badgeEl.style.display = 'inline-block';
                contentEl.innerHTML = `<div class="lyrics-plain">${escapeHtml(res.plain)}</div>`;
            } else {
                badgeEl.style.display = 'none';
                contentEl.innerHTML = `<p class="lyrics-placeholder">No lyrics available for this song</p>`;
            }
        } catch (error) {
            loadingEl.classList.add('hidden');
            contentEl.innerHTML = `<p class="lyrics-placeholder">Could not load lyrics</p>`;
        }
    },

    renderSynced() {
        const contentEl = document.getElementById('lyrics-content');
        contentEl.innerHTML = this.syncedLines.map((line, index) => `
            <div class="lyrics-line" id="lyric-line-${index}" onclick="Lyrics.seekToLine(${index})">
                ${escapeHtml(line.text)}
            </div>
        `).join('');
    },

    seekToLine(index) {
        if (this.syncedLines[index] && Player?.audio) {
            Player.audio.currentTime = this.syncedLines[index].time;
        }
    },

    syncToTime(currentTime) {
        if (!this.syncedLines || this.syncedLines.length === 0) return;

        // Find current active line
        let newIndex = -1;
        for (let i = 0; i < this.syncedLines.length; i++) {
            if (currentTime >= this.syncedLines[i].time) {
                newIndex = i;
            } else {
                break;
            }
        }

        if (newIndex !== this.activeIndex && newIndex >= 0) {
            // Remove previous active
            if (this.activeIndex >= 0) {
                document.getElementById(`lyric-line-${this.activeIndex}`)?.classList.remove('active');
            }

            // Set new active
            const currentEl = document.getElementById(`lyric-line-${newIndex}`);
            if (currentEl) {
                currentEl.classList.add('active');
                // Smooth scroll to keep active line centered
                currentEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }

            this.activeIndex = newIndex;
        }
    }
};
