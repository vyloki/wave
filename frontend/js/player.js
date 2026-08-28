/**
 * Wave — Music Player Engine
 * Full audio engine with continuous recommendation playback, queue, lyrics sync,
 * Media Session API, volume control, progress seeking, and persistent dual-layer history.
 */

const Player = {
    audio: null,
    currentTrack: null,
    queue: [],
    queueIndex: -1,
    isPlaying: false,
    repeatMode: 'off', // off, all, one
    shuffleEnabled: false,
    volume: 80,
    elements: {},

    init() {
        this.audio = new Audio();
        this.audio.crossOrigin = 'anonymous';
        this.audio.preload = 'auto';
        this.audio.volume = this.volume / 100;

        this.cacheElements();
        this.bindEvents();
        this.bindAudioEvents();
        this.setupMediaSession();

        const savedVolume = localStorage.getItem('wave_volume');
        if (savedVolume !== null) {
            this.volume = parseInt(savedVolume);
            this.audio.volume = this.volume / 100;
            if (this.elements.volumeSlider) {
                this.elements.volumeSlider.value = this.volume;
            }
        }
    },

    cacheElements() {
        this.elements = {
            playBtn: document.getElementById('btn-play'),
            prevBtn: document.getElementById('btn-prev'),
            nextBtn: document.getElementById('btn-next'),
            shuffleBtn: document.getElementById('btn-shuffle'),
            repeatBtn: document.getElementById('btn-repeat'),
            likeBtn: document.getElementById('btn-like'),
            lyricsBtn: document.getElementById('btn-lyrics'),
            volumeBtn: document.getElementById('btn-volume'),
            volumeSlider: document.getElementById('volume-slider'),
            progressContainer: document.getElementById('progress-container'),
            progressFill: document.getElementById('progress-fill'),
            progressThumb: document.getElementById('progress-thumb'),
            timeCurrent: document.getElementById('time-current'),
            timeDuration: document.getElementById('time-duration'),
            trackName: document.getElementById('player-track-name'),
            artist: document.getElementById('player-artist'),
            artImg: document.getElementById('player-art-img'),
            artContainer: document.getElementById('player-art'),
            trackInfo: document.getElementById('player-track-info'),
            barsIndicator: document.getElementById('player-bars-indicator'),
            downloadBtn: document.getElementById('btn-download'),
        };
    },

    bindEvents() {
        this.elements.playBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.togglePlay();
        });
        this.elements.prevBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.previous();
        });
        this.elements.nextBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.next();
        });
        this.elements.shuffleBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleShuffle();
        });
        this.elements.repeatBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleRepeat();
        });
        this.elements.likeBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleLike();
        });
        this.elements.downloadBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            if (this.currentTrack) {
                downloadSong(
                    this.currentTrack.video_id,
                    this.currentTrack.track_name || this.currentTrack.title,
                    this.currentTrack.artist
                );
            }
        });

        // Clicking on the currently playing track info opens the lyrics & now-playing view
        this.elements.trackInfo?.addEventListener('click', (e) => {
            if (e.target.closest('#player-artist')) {
                e.stopPropagation();
                if (this.currentTrack?.artist && typeof openArtistPage === 'function') {
                    openArtistPage(this.currentTrack.artist);
                }
                return;
            }
            if (!e.target.closest('#btn-like') && !e.target.closest('#btn-download')) {
                this.toggleLyrics();
            }
        });

        // Lyrics button
        this.elements.lyricsBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleLyrics();
        });

        document.getElementById('btn-lyrics-close')?.addEventListener('click', () => {
            document.getElementById('lyrics-overlay')?.classList.add('hidden');
        });

        // Volume
        this.elements.volumeSlider?.addEventListener('input', (e) => {
            this.setVolume(parseInt(e.target.value));
        });
        this.elements.volumeBtn?.addEventListener('click', () => this.toggleMute());

        // Progress bar seeking
        this.elements.progressContainer?.addEventListener('click', (e) => {
            const rect = this.elements.progressContainer.getBoundingClientRect();
            const percent = (e.clientX - rect.left) / rect.width;
            this.seekTo(percent);
        });

        // Clear queue
        document.getElementById('btn-clear-queue')?.addEventListener('click', () => {
            this.clearQueue();
        });

        // Queue button in player
        document.getElementById('btn-queue')?.addEventListener('click', () => {
            navigateTo('queue');
        });
    },

    toggleLyrics() {
        const overlay = document.getElementById('lyrics-overlay');
        if (!overlay) return;

        overlay.classList.toggle('hidden');
        if (!overlay.classList.contains('hidden') && this.currentTrack) {
            if (typeof Lyrics !== 'undefined') {
                Lyrics.loadLyrics(this.currentTrack);
            }
        }
    },

    bindAudioEvents() {
        this.audio.addEventListener('timeupdate', () => this.onTimeUpdate());
        this.audio.addEventListener('loadedmetadata', () => this.onLoaded());
        this.audio.addEventListener('ended', () => this.onEnded());
        this.audio.addEventListener('play', () => this.onPlayState(true));
        this.audio.addEventListener('pause', () => this.onPlayState(false));
        this.audio.addEventListener('error', (e) => this.onError(e));
    },

    // ============================================
    // Playback
    // ============================================

    async play(track) {
        if (!track || !track.video_id) return;

        const prevTrackId = this.currentTrack?.video_id;
        this.currentTrack = track;
        this.updateTrackUI(track);

        // Save track to local storage recently played
        if (!track.isLocal) {
            this.saveToLocalHistory(track);
        }

        // Set audio stream URL (local blob or backend proxy)
        if (track.isLocal && track.objectUrl) {
            this.audio.src = track.objectUrl;
        } else {
            this.audio.src = `/api/stream/${track.video_id}`;
        }

        try {
            await this.audio.play();
            this.isPlaying = true;
            this.onPlayState(true);

            // Record transition in graph (for online songs)
            if (!track.isLocal && prevTrackId && prevTrackId !== track.video_id) {
                API.post(`/api/recommendations/transition?from_id=${prevTrackId}&to_id=${track.video_id}`).catch(() => {});
            }

            // Record history in MongoDB (for online songs)
            if (!track.isLocal) {
                API.post('/api/history', {
                    video_id: track.video_id,
                    title: track.track_name || track.title || 'Unknown',
                    artist: track.artist || 'Unknown',
                    thumbnail: track.thumbnail || track.album_art || '',
                }).catch(() => {});
            }

            // Update Media Session
            this.updateMediaSession(track);

            // Refresh recently played on Home
            if (typeof loadHomeRecentlyPlayed === 'function') {
                loadHomeRecentlyPlayed();
            }

            // Auto-refresh lyrics if overlay is open
            if (!document.getElementById('lyrics-overlay')?.classList.contains('hidden')) {
                if (typeof Lyrics !== 'undefined') {
                    Lyrics.loadLyrics(track);
                }
            }

            // Check if liked
            this.checkLikeStatus(track.video_id);

        } catch (error) {
            console.error('Audio play error:', error);
            showToast('Unable to stream audio for this track', 'error');
        }
    },

    togglePlay() {
        if (!this.audio.src) {
            if (this.queue.length > 0) {
                this.play(this.queue[0]);
            }
            return;
        }

        if (this.isPlaying) {
            this.audio.pause();
        } else {
            this.audio.play().catch(console.error);
        }
    },

    async next() {
        if (this.queue.length === 0 && !this.currentTrack) return;

        if (this.shuffleEnabled && this.queue.length > 1) {
            let randomIndex;
            do {
                randomIndex = Math.floor(Math.random() * this.queue.length);
            } while (randomIndex === this.queueIndex && this.queue.length > 1);
            this.queueIndex = randomIndex;
            this.play(this.queue[this.queueIndex]);
            return;
        }

        this.queueIndex++;
        if (this.queueIndex < this.queue.length) {
            this.play(this.queue[this.queueIndex]);
        } else if (this.repeatMode === 'all' && this.queue.length > 0) {
            this.queueIndex = 0;
            this.play(this.queue[0]);
        } else if (this.currentTrack) {
            try {
                const data = await API.get(`/api/recommendations/next?current_id=${this.currentTrack.video_id}`);
                if (data && data.track && data.track.video_id) {
                    this.queue.push(data.track);
                    this.queueIndex = this.queue.length - 1;
                    this.play(data.track);
                    this.renderQueue();
                    showToast(`Autoplaying: ${data.track.track_name || data.track.title}`, 'info');
                    return;
                }
            } catch (e) {
                console.debug('Autoplay recommendation failed:', e);
            }
            this.queueIndex = this.queue.length - 1;
        }
    },

    previous() {
        if (this.audio.currentTime > 3) {
            this.audio.currentTime = 0;
            return;
        }

        if (this.queueIndex > 0) {
            this.queueIndex--;
            this.play(this.queue[this.queueIndex]);
        }
    },

    seekTo(percent) {
        if (this.audio.duration) {
            this.audio.currentTime = percent * this.audio.duration;
        }
    },

    seekRelative(seconds) {
        if (this.audio.duration) {
            this.audio.currentTime = Math.max(
                0,
                Math.min(this.audio.duration, this.audio.currentTime + seconds)
            );
        }
    },

    // ============================================
    // Persistent History
    // ============================================

    saveToLocalHistory(track) {
        try {
            const raw = localStorage.getItem('wave_recently_played');
            let list = raw ? JSON.parse(raw) : [];

            list = list.filter(t => t.video_id !== track.video_id);

            list.unshift({
                video_id: track.video_id,
                title: track.track_name || track.title || 'Unknown',
                track_name: track.track_name || track.title || 'Unknown',
                artist: track.artist || 'Unknown',
                thumbnail: track.thumbnail || track.album_art || '',
                album_art: track.thumbnail || track.album_art || '',
                duration: track.duration || 0,
                played_at: new Date().toISOString(),
            });

            list = list.slice(0, 30);
            localStorage.setItem('wave_recently_played', JSON.stringify(list));
        } catch (e) {
            console.debug('Failed to save local history:', e);
        }
    },

    // ============================================
    // Queue
    // ============================================

    setQueue(tracks, startIndex = 0) {
        this.queue = [...tracks];
        this.queueIndex = startIndex;
        this.renderQueue();
    },

    addToQueue(track) {
        this.queue.push(track);
        this.renderQueue();
    },

    clearQueue() {
        const current = this.queue[this.queueIndex];
        this.queue = current ? [current] : [];
        this.queueIndex = 0;
        this.renderQueue();
        showToast('Queue cleared', 'info');
    },

    renderQueue() {
        const container = document.getElementById('queue-list');
        if (!container) return;

        if (this.queue.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i data-lucide="list-music"></i>
                    <p>Your queue is empty</p>
                </div>
            `;
            lucide.createIcons({ nodes: [container] });
            return;
        }

        container.innerHTML = this.queue.map((track, i) => `
            <div class="track-row ${i === this.queueIndex ? 'playing' : ''}"
                 onclick="Player.play(Player.queue[${i}]); Player.queueIndex = ${i};">
                <div class="track-row-art">
                    <img src="${track.thumbnail || track.album_art || ''}"
                         alt="" loading="lazy"
                         onerror="this.style.display='none'">
                </div>
                <div class="track-row-info">
                    <div class="track-row-title">${escapeHtml(track.track_name || track.title)}</div>
                    <div class="track-row-artist">${escapeHtml(track.artist)}</div>
                </div>
                <div class="track-row-duration">${formatDuration(track.duration)}</div>
            </div>
        `).join('');

        lucide.createIcons({ nodes: [container] });
    },

    // ============================================
    // Volume
    // ============================================

    setVolume(value) {
        this.volume = Math.max(0, Math.min(100, value));
        this.audio.volume = this.volume / 100;
        localStorage.setItem('wave_volume', this.volume);
        this.updateVolumeIcon();
    },

    adjustVolume(delta) {
        this.setVolume(this.volume + delta);
        if (this.elements.volumeSlider) {
            this.elements.volumeSlider.value = this.volume;
        }
    },

    toggleMute() {
        if (this.audio.volume > 0) {
            this._prevVol = this.volume;
            this.setVolume(0);
        } else {
            this.setVolume(this._prevVol || 80);
        }
        if (this.elements.volumeSlider) {
            this.elements.volumeSlider.value = this.volume;
        }
    },

    updateVolumeIcon() {
        const btn = this.elements.volumeBtn;
        if (!btn) return;

        let iconName = 'volume-2';
        if (this.volume === 0) iconName = 'volume-x';
        else if (this.volume < 50) iconName = 'volume-1';

        btn.innerHTML = `<i data-lucide="${iconName}"></i>`;
        lucide.createIcons({ nodes: [btn] });
    },

    // ============================================
    // Shuffle & Repeat
    // ============================================

    toggleShuffle() {
        this.shuffleEnabled = !this.shuffleEnabled;
        this.elements.shuffleBtn?.classList.toggle('active', this.shuffleEnabled);
        showToast(this.shuffleEnabled ? 'Shuffle on' : 'Shuffle off', 'info');
    },

    toggleRepeat() {
        const modes = ['off', 'all', 'one'];
        const idx = modes.indexOf(this.repeatMode);
        this.repeatMode = modes[(idx + 1) % modes.length];

        const btn = this.elements.repeatBtn;
        btn?.classList.toggle('active', this.repeatMode !== 'off');
        btn?.classList.toggle('repeat-one', this.repeatMode === 'one');

        const labels = { off: 'Repeat off', all: 'Repeat all', one: 'Repeat one' };
        showToast(labels[this.repeatMode], 'info');
    },

    // ============================================
    // Likes
    // ============================================

    async toggleLike() {
        if (!this.currentTrack) return;

        try {
            await API.post(`/api/auth/like/${this.currentTrack.video_id}`);
            this.elements.likeBtn?.classList.toggle('liked');
            const isLiked = this.elements.likeBtn?.classList.contains('liked');
            showToast(isLiked ? 'Added to Liked Songs' : 'Removed from Liked Songs', 'success');
        } catch {
            showToast('Sign in to save liked songs', 'info');
        }
    },

    async checkLikeStatus(videoId) {
        try {
            const user = await API.get('/api/auth/me');
            if (user && user.liked_tracks) {
                const isLiked = user.liked_tracks.includes(videoId);
                this.elements.likeBtn?.classList.toggle('liked', isLiked);
            }
        } catch {}
    },

    // ============================================
    // Audio Events & State Toggles
    // ============================================

    onTimeUpdate() {
        if (!this.audio.duration) return;

        const percent = (this.audio.currentTime / this.audio.duration) * 100;
        if (this.elements.progressFill) {
            this.elements.progressFill.style.width = `${percent}%`;
        }

        if (this.elements.timeCurrent) {
            this.elements.timeCurrent.textContent = formatDuration(this.audio.currentTime);
        }

        if (typeof Lyrics !== 'undefined') {
            Lyrics.syncToTime(this.audio.currentTime);
        }
    },

    onLoaded() {
        if (this.elements.timeDuration) {
            this.elements.timeDuration.textContent = formatDuration(this.audio.duration);
        }
    },

    onEnded() {
        if (this.repeatMode === 'one') {
            this.audio.currentTime = 0;
            this.audio.play();
        } else {
            this.next();
        }
    },

    onPlayState(playing) {
        this.isPlaying = playing;

        // Clean, reliable Play/Pause button icon change
        const btn = this.elements.playBtn;
        if (btn) {
            btn.innerHTML = `<i data-lucide="${playing ? 'pause' : 'play'}"></i>`;
            lucide.createIcons({ nodes: [btn] });
        }

        // Show/hide animated waveform equalizer bars
        if (this.elements.barsIndicator) {
            this.elements.barsIndicator.classList.toggle('hidden', !playing);
        }

        // Highlight active track rows
        document.querySelectorAll('.track-row').forEach(row => {
            row.classList.toggle('playing', row.dataset.videoId === this.currentTrack?.video_id);
        });
    },

    onError(e) {
        console.error('Audio stream playback error:', e);
    },

    // ============================================
    // UI Updates
    // ============================================

    updateTrackUI(track) {
        const name = track.track_name || track.title || 'Unknown';
        const artist = track.artist || 'Unknown Artist';
        const art = track.thumbnail || track.album_art || '';

        if (this.elements.trackName) this.elements.trackName.textContent = name;
        if (this.elements.artist) this.elements.artist.textContent = artist;

        if (this.elements.artImg && art) {
            this.elements.artImg.src = art;
            this.elements.artContainer?.classList.add('has-art');
        } else {
            this.elements.artContainer?.classList.remove('has-art');
        }

        if (this.elements.progressFill) this.elements.progressFill.style.width = '0%';
        if (this.elements.timeCurrent) this.elements.timeCurrent.textContent = '0:00';
        if (this.elements.timeDuration && track.duration) {
            this.elements.timeDuration.textContent = formatDuration(track.duration);
        }

        document.title = `▶ ${name} — ${artist} | Wave`;

        document.querySelectorAll('.track-row').forEach(row => {
            row.classList.toggle('playing', row.dataset.videoId === track.video_id);
        });
    },

    // ============================================
    // Media Session API
    // ============================================

    setupMediaSession() {
        if ('mediaSession' in navigator) {
            navigator.mediaSession.setActionHandler('play', () => this.togglePlay());
            navigator.mediaSession.setActionHandler('pause', () => this.togglePlay());
            navigator.mediaSession.setActionHandler('previoustrack', () => this.previous());
            navigator.mediaSession.setActionHandler('nexttrack', () => this.next());
            navigator.mediaSession.setActionHandler('seekto', (details) => {
                if (details.seekTime !== undefined) {
                    this.audio.currentTime = details.seekTime;
                }
            });
        }
    },

    updateMediaSession(track) {
        if ('mediaSession' in navigator) {
            navigator.mediaSession.metadata = new MediaMetadata({
                title: track.track_name || track.title || 'Unknown',
                artist: track.artist || 'Unknown Artist',
                artwork: [
                    {
                        src: track.thumbnail || track.album_art || '',
                        sizes: '512x512',
                        type: 'image/jpeg',
                    },
                ],
            });
        }
    },
};

document.addEventListener('DOMContentLoaded', () => {
    Player.init();
});
