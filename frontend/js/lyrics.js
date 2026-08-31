/**
 * Wave — Synced Lyrics Module
 * Fetches lyrics from LRCLIB and syncs line highlighting to audio playback time.
 * Supports real-time manual sync calibration (+/- offset) persisted per track.
 */

const Lyrics = {
    syncedLines: [],
    activeIndex: -1,
    currentTrackId: null,
    syncOffset: 0.0,

    async loadLyrics(track) {
        if (!track || !track.video_id) return;

        const overlay = document.getElementById('lyrics-overlay');
        const contentEl = document.getElementById('lyrics-content');
        const loadingEl = document.getElementById('lyrics-loading');
        const badgeEl = document.getElementById('lyrics-badge');
        const syncControls = document.getElementById('lyrics-sync-controls');

        // Update header & artwork
        document.getElementById('lyrics-track-name').textContent = track.track_name || track.title || 'Unknown';
        document.getElementById('lyrics-artist').textContent = track.artist || 'Unknown Artist';

        const artImg = document.getElementById('lyrics-art-img');
        const artFrame = document.getElementById('lyrics-art-frame');
        const art = track.thumbnail || track.album_art || '';
        if (artImg) {
            if (art) {
                artImg.src = art;
                artFrame?.classList.add('has-art');
            } else {
                artImg.src = '';
                artFrame?.classList.remove('has-art');
            }
        }

        this.currentTrackId = track.video_id;
        this.syncedLines = [];
        this.activeIndex = -1;

        // Load saved sync calibration offset for this song
        const savedOffset = localStorage.getItem(`wave_lyrics_offset_${track.video_id}`);
        this.syncOffset = savedOffset !== null ? parseFloat(savedOffset) : 0.0;
        this.updateOffsetUI();

        loadingEl.classList.remove('hidden');
        contentEl.innerHTML = '';

        try {
            const title = encodeURIComponent(track.track_name || track.title || '');
            const artist = encodeURIComponent(track.artist || '');
            const movie = encodeURIComponent(track.movie || track.album || '');
            const duration = track.duration || 0;
            const language = encodeURIComponent(track.language || '');

            const res = await API.get(`/api/lyrics/${track.video_id}?title=${title}&artist=${artist}&movie=${movie}&duration=${duration}&language=${language}`);
            loadingEl.classList.add('hidden');

            if (res && res.has_synced && res.synced && res.synced.length > 0) {
                this.syncedLines = res.synced;
                badgeEl.textContent = 'Synced Lyrics';
                badgeEl.style.display = 'inline-block';
                if (syncControls) syncControls.classList.remove('hidden');
                this.renderSynced();
            } else if (res && res.plain) {
                badgeEl.textContent = 'Plain Lyrics';
                badgeEl.style.display = 'inline-block';
                if (syncControls) syncControls.classList.add('hidden');
                contentEl.innerHTML = `<div class="lyrics-plain">${escapeHtml(res.plain)}</div>`;
            } else {
                badgeEl.style.display = 'none';
                if (syncControls) syncControls.classList.add('hidden');
                contentEl.innerHTML = `<p class="lyrics-placeholder">No lyrics available for this song</p>`;
            }
        } catch (error) {
            loadingEl.classList.add('hidden');
            if (syncControls) syncControls.classList.add('hidden');
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
        if (this.syncedLines[index] && typeof Player !== 'undefined') {
            const targetTime = Math.max(0, this.syncedLines[index].time + this.syncOffset);
            Player.seekToSeconds(targetTime);
        }
    },

    adjustOffset(delta) {
        this.syncOffset = Math.round((this.syncOffset + delta) * 10) / 10;
        if (this.currentTrackId) {
            localStorage.setItem(`wave_lyrics_offset_${this.currentTrackId}`, this.syncOffset);
        }
        this.updateOffsetUI();
        showToast(`Lyrics sync: ${this.syncOffset > 0 ? '+' : ''}${this.syncOffset.toFixed(1)}s`, 'info');

        // Force re-sync with current playback time
        const curTime = (Player?.activeEngine === 'yt' && Player.YTBridge?.player?.getCurrentTime)
            ? Player.YTBridge.player.getCurrentTime()
            : (Player?.audio?.currentTime || 0);
        this.activeIndex = -1;
        this.syncToTime(curTime);
    },

    resetOffset() {
        this.syncOffset = 0.0;
        if (this.currentTrackId) {
            localStorage.removeItem(`wave_lyrics_offset_${this.currentTrackId}`);
        }
        this.updateOffsetUI();
        showToast('Lyrics sync reset to 0.0s', 'info');

        const curTime = (Player?.activeEngine === 'yt' && Player.YTBridge?.player?.getCurrentTime)
            ? Player.YTBridge.player.getCurrentTime()
            : (Player?.audio?.currentTime || 0);
        this.activeIndex = -1;
        this.syncToTime(curTime);
    },

    updateOffsetUI() {
        const valEl = document.getElementById('sync-offset-val');
        const sheetValEl = document.getElementById('lyrics-sheet-sync-val');
        const prefix = this.syncOffset > 0 ? '+' : '';
        const txt = `${prefix}${this.syncOffset.toFixed(1)}s`;
        if (valEl) valEl.textContent = txt;
        if (sheetValEl) sheetValEl.textContent = txt;
    },

    syncToTime(currentTime) {
        if (!this.syncedLines || this.syncedLines.length === 0) return;

        // Calibrated time calculation
        const calibratedTime = currentTime - this.syncOffset;

        // Find current active line
        let newIndex = -1;
        for (let i = 0; i < this.syncedLines.length; i++) {
            if (calibratedTime >= this.syncedLines[i].time) {
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
