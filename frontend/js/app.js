/**
 * Wave — Main Application Logic
 * SPA routing, state management, API client, Home feed loader, search,
 * artist profiles, and persistent recently played rendering.
 */

// ============================================
// API Client
// ============================================

const API = {
    baseUrl: '',

    getHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        const token = localStorage.getItem('wave_access_token');
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        return headers;
    },

    async request(method, url, body = null) {
        const options = {
            method,
            headers: this.getHeaders(),
        };
        if (body) {
            options.body = JSON.stringify(body);
        }

        try {
            const response = await fetch(`${this.baseUrl}${url}`, options);

            // Handle token expiry
            if (response.status === 401 && !url.includes('/api/auth/login') && !url.includes('/api/auth/register')) {
                const refreshed = await Auth.refreshToken();
                if (refreshed) {
                    options.headers = this.getHeaders();
                    const retryResponse = await fetch(`${this.baseUrl}${url}`, options);
                    return await retryResponse.json();
                } else {
                    return null;
                }
            }

            if (!response.ok) {
                const error = await response.json().catch(() => ({}));
                throw new Error(error.detail || `HTTP ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.debug(`API Error [${method} ${url}]:`, error);
            throw error;
        }
    },

    get(url) { return this.request('GET', url); },
    post(url, body) { return this.request('POST', url, body); },
    put(url, body) { return this.request('PUT', url, body); },
    delete(url) { return this.request('DELETE', url); },
};


// ============================================
// App State
// ============================================

const AppState = {
    currentPage: 'home',
    user: null,
    isAuthenticated: false,
    searchResults: [],
    searchTimeout: null,
    categories: [],
    currentArtist: null,
};


// ============================================
// Toast Notifications
// ============================================

function showToast(message, type = 'info', duration = 3000) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}


// ============================================
// Navigation / Routing
// ============================================

function navigateTo(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));

    const targetPage = document.getElementById(`page-${page}`);
    if (targetPage) {
        targetPage.classList.add('active');
    }

    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.toggle('active', item.dataset.page === page);
    });

    AppState.currentPage = page;

    if (page === 'search') {
        setTimeout(() => {
            document.getElementById('search-input')?.focus();
        }, 100);
    } else if (page === 'library') {
        if (typeof Library !== 'undefined') {
            Library.renderTabContent();
        }
    } else if (page === 'home') {
        loadHomeRecentlyPlayed();
    }
}


// ============================================
// Home Page Feed & Categories
// ============================================

async function initHomeFeed() {
    updateGreeting();
    loadHomeRecentlyPlayed();
    loadFeaturedArtists();

    try {
        const feed = await API.get('/api/recommendations/feed');
        if (feed) {
            if (feed.categories) {
                AppState.categories = feed.categories;
                renderCategoryPills(feed.categories);
                renderSearchBrowseTags(feed.categories);
            }

            if (feed.trending && feed.trending.length > 0) {
                renderTrackCards(feed.trending, 'trending-scroll');
            }
            if (feed.telugu && feed.telugu.length > 0) {
                renderTrackCards(feed.telugu, 'telugu-scroll');
            }
            if (feed.hindi && feed.hindi.length > 0) {
                renderTrackCards(feed.hindi, 'hindi-scroll');
            }
            if (feed.english && feed.english.length > 0) {
                renderTrackCards(feed.english, 'english-scroll');
            }
            if (feed.lofi && feed.lofi.length > 0) {
                renderTrackCards(feed.lofi, 'lofi-scroll');
            }
        }
    } catch (e) {
        console.debug('Home feed error:', e);
    }
}

// ============================================
// Featured Artists & Artist Profiles
// ============================================

async function loadFeaturedArtists() {
    const container = document.getElementById('artists-scroll');
    if (!container) return;

    try {
        const artists = await API.get('/api/artists/featured');
        if (artists && artists.length > 0) {
            container.innerHTML = artists.map(artist => `
                <div class="artist-card" onclick="openArtistPage('${escapeHtml(artist.name)}')">
                    <div class="artist-card-avatar">
                        <img src="${artist.image}" alt="${escapeHtml(artist.name)}" loading="lazy">
                    </div>
                    <div class="artist-card-name">${escapeHtml(artist.name)}</div>
                    <div class="artist-card-genre">${escapeHtml(artist.genre || 'Artist')}</div>
                </div>
            `).join('');
        }
    } catch (e) {
        console.debug('Failed to load featured artists:', e);
    }
}

async function openArtistPage(artistName) {
    if (!artistName || artistName === 'Unknown Artist' || artistName === 'Wave Music') return;

    navigateTo('artist-detail');

    const nameEl = document.getElementById('artist-detail-name');
    const genreEl = document.getElementById('artist-detail-genre');
    const metaEl = document.getElementById('artist-detail-meta');
    const avatarEl = document.getElementById('artist-detail-avatar');
    const listEl = document.getElementById('artist-track-list');

    if (nameEl) nameEl.textContent = artistName;
    if (genreEl) genreEl.textContent = 'Loading artist profile...';
    if (metaEl) metaEl.textContent = 'Fetching songs...';
    if (listEl) {
        listEl.innerHTML = `
            <div class="loading-state">
                <div class="loader">
                    <div class="loader-bar"></div>
                    <div class="loader-bar"></div>
                    <div class="loader-bar"></div>
                </div>
                <p>Loading songs by ${escapeHtml(artistName)}...</p>
            </div>
        `;
    }

    try {
        const data = await API.get(`/api/artists/${encodeURIComponent(artistName)}`);
        if (data) {
            AppState.currentArtist = data;

            if (nameEl) nameEl.textContent = data.artist;
            if (genreEl) genreEl.textContent = data.genre || 'Popular Artist';
            if (metaEl) metaEl.textContent = `${data.total_tracks || data.tracks?.length || 0} songs available`;

            if (avatarEl && data.image) {
                avatarEl.innerHTML = `<img src="${data.image}" alt="${escapeHtml(data.artist)}">`;
            }

            if (data.tracks && data.tracks.length > 0) {
                renderArtistTracks(data.tracks);

                // Bind Play All & Shuffle
                document.getElementById('btn-play-artist-all').onclick = () => {
                    Player.setQueue(data.tracks, 0);
                    Player.play(data.tracks[0]);
                };

                document.getElementById('btn-shuffle-artist').onclick = () => {
                    Player.setQueue(data.tracks, 0);
                    Player.shuffleEnabled = true;
                    Player.play(data.tracks[Math.floor(Math.random() * data.tracks.length)]);
                };
            } else {
                if (listEl) {
                    listEl.innerHTML = `<div class="empty-state"><p>No songs found for ${escapeHtml(artistName)}</p></div>`;
                }
            }
        }
    } catch (error) {
        if (listEl) {
            listEl.innerHTML = `<div class="empty-state"><p>Failed to load songs for ${escapeHtml(artistName)}</p></div>`;
        }
    }
}

function renderArtistTracks(tracks) {
    const listEl = document.getElementById('artist-track-list');
    if (!listEl) return;

    listEl.innerHTML = `
        <div class="track-list">
            ${tracks.map((track, index) => `
                <div class="track-row"
                     data-video-id="${track.video_id}"
                     onclick="playTrackFromArtist(${index})">
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
                    <div class="track-row-actions">
                        <button class="btn-icon" onclick="event.stopPropagation(); downloadSong('${track.video_id}', '${escapeHtml(track.track_name || track.title)}', '${escapeHtml(track.artist)}')" title="Download">
                            <i data-lucide="download"></i>
                        </button>
                        <button class="btn-icon" onclick="event.stopPropagation(); addToQueueFromArtist(${index})" title="Add to queue">
                            <i data-lucide="list-plus"></i>
                        </button>
                        <button class="btn-icon" onclick="event.stopPropagation(); Library.openAddToPlaylistModal('${track.video_id}', ${JSON.stringify(track).replace(/"/g, '&quot;')})" title="Add to playlist">
                            <i data-lucide="plus"></i>
                        </button>
                    </div>
                </div>
            `).join('')}
        </div>
    `;

    lucide.createIcons({ nodes: [listEl] });
}

function playTrackFromArtist(index) {
    if (AppState.currentArtist?.tracks) {
        Player.setQueue(AppState.currentArtist.tracks, index);
        Player.play(AppState.currentArtist.tracks[index]);
    }
}

function addToQueueFromArtist(index) {
    if (AppState.currentArtist?.tracks) {
        const track = AppState.currentArtist.tracks[index];
        Player.addToQueue(track);
        showToast(`Added "${track.track_name || track.title}" to queue`, 'success');
    }
}


function renderCategoryPills(categories) {
    const container = document.getElementById('home-categories');
    if (!container) return;

    container.innerHTML = categories.map(cat => `
        <button class="category-pill" onclick="loadCategoryTracks('${cat.id}')">
            <i data-lucide="${cat.icon || 'music'}"></i>
            <span>${escapeHtml(cat.name)}</span>
        </button>
    `).join('');

    lucide.createIcons({ nodes: [container] });
}

function renderSearchBrowseTags(categories) {
    const container = document.getElementById('search-browse-tags');
    if (!container) return;

    container.innerHTML = categories.map(cat => `
        <button class="category-pill" onclick="searchForCategory('${escapeHtml(cat.name)}')">
            <i data-lucide="${cat.icon || 'music'}"></i>
            <span>${escapeHtml(cat.name)}</span>
        </button>
    `).join('');

    lucide.createIcons({ nodes: [container] });
}

function searchForCategory(categoryName) {
    const input = document.getElementById('search-input');
    if (input) {
        input.value = categoryName;
        document.getElementById('search-clear')?.classList.remove('hidden');
        performSearch(categoryName);
    }
}

async function loadCategoryTracks(categoryId) {
    const cat = AppState.categories.find(c => c.id === categoryId);
    if (cat) {
        navigateTo('search');
        searchForCategory(cat.name);
    }
}

// ============================================
// Dual-Layer Recently Played (Local + Cloud)
// ============================================

async function loadHomeRecentlyPlayed() {
    const container = document.getElementById('recent-scroll');
    if (!container) return;

    let tracks = [];

    // 1. First load from localStorage (instant, never lost across logouts)
    try {
        const raw = localStorage.getItem('wave_recently_played');
        if (raw) {
            tracks = JSON.parse(raw);
        }
    } catch (e) {}

    // 2. If authenticated, attempt to fetch from MongoDB Atlas
    if (AppState.isAuthenticated) {
        try {
            const data = await API.get('/api/history?limit=10');
            if (data && data.history && data.history.length > 0) {
                const cloudTracks = data.history.map(h => ({
                    video_id: h.video_id,
                    title: h.title,
                    track_name: h.title,
                    artist: h.artist,
                    thumbnail: h.thumbnail,
                    album_art: h.thumbnail,
                    duration: 0,
                }));

                // Merge deduplicating by video_id
                const seen = new Set();
                const merged = [];
                for (const t of [...tracks, ...cloudTracks]) {
                    if (t && t.video_id && !seen.has(t.video_id)) {
                        seen.add(t.video_id);
                        merged.push(t);
                    }
                }
                tracks = merged.slice(0, 15);
            }
        } catch (e) {}
    }

    if (tracks.length > 0) {
        renderTrackCards(tracks, 'recent-scroll');
    } else {
        container.innerHTML = `
            <div class="empty-state-card">
                <i data-lucide="music"></i>
                <p>Play a song to see it here</p>
            </div>
        `;
        lucide.createIcons({ nodes: [container] });
    }
}


// ============================================
// Search Functionality
// ============================================

let searchDebounceTimer = null;

async function performSearch(query) {
    if (!query || query.trim().length === 0) return;

    const resultsContainer = document.getElementById('search-results');
    const loadingEl = document.getElementById('search-loading');
    const suggestionsEl = document.getElementById('search-suggestions');
    const browseTagsEl = document.getElementById('search-browse-tags');

    suggestionsEl?.classList.add('hidden');
    browseTagsEl?.classList.add('hidden');
    loadingEl?.classList.remove('hidden');
    resultsContainer.innerHTML = '';

    try {
        const data = await API.get(`/api/search?q=${encodeURIComponent(query.trim())}&limit=25`);

        loadingEl?.classList.add('hidden');

        if (data && data.results && data.results.length > 0) {
            AppState.searchResults = data.results;
            renderSearchResults(data.results);
        } else {
            resultsContainer.innerHTML = `
                <div class="empty-state">
                    <i data-lucide="search-x"></i>
                    <p>No results found for "${escapeHtml(query)}"</p>
                </div>
            `;
            lucide.createIcons({ nodes: [resultsContainer] });
        }
    } catch (error) {
        loadingEl?.classList.add('hidden');
        resultsContainer.innerHTML = `
            <div class="empty-state">
                <i data-lucide="wifi-off"></i>
                <p>Search failed. Please verify the Python server is running.</p>
            </div>
        `;
        lucide.createIcons({ nodes: [resultsContainer] });
    }
}

function renderSearchResults(results) {
    const container = document.getElementById('search-results');
    container.innerHTML = `
        <div class="track-list">
            ${results.map((track, index) => `
                <div class="track-row"
                     data-video-id="${track.video_id}"
                     onclick="playTrackFromResults(${index})">
                    <div class="track-row-art">
                        <img src="${track.thumbnail || track.album_art || ''}"
                             alt=""
                             loading="lazy"
                             onerror="this.style.display='none'">
                    </div>
                    <div class="track-row-info">
                        <div class="track-row-title">${escapeHtml(track.track_name || track.title)}</div>
                        <div class="track-row-artist" onclick="event.stopPropagation(); openArtistPage('${escapeHtml(track.artist)}')">${escapeHtml(track.artist)}</div>
                    </div>
                    <div class="track-row-duration">${formatDuration(track.duration)}</div>
                    <div class="track-row-actions">
                        <button class="btn-icon" onclick="event.stopPropagation(); downloadSong('${track.video_id}', '${escapeHtml(track.track_name || track.title)}', '${escapeHtml(track.artist)}')" title="Download">
                            <i data-lucide="download"></i>
                        </button>
                        <button class="btn-icon" onclick="event.stopPropagation(); addToQueue(${index})" title="Add to queue">
                            <i data-lucide="list-plus"></i>
                        </button>
                        <button class="btn-icon" onclick="event.stopPropagation(); Library.openAddToPlaylistModal('${track.video_id}', ${JSON.stringify(track).replace(/"/g, '&quot;')})" title="Add to playlist">
                            <i data-lucide="plus"></i>
                        </button>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
    lucide.createIcons({ nodes: [container] });
}

async function fetchSuggestions(query) {
    if (!query || query.length < 2) {
        document.getElementById('search-suggestions')?.classList.add('hidden');
        return;
    }

    try {
        const data = await API.get(`/api/search/suggestions?q=${encodeURIComponent(query)}`);
        if (data && data.suggestions && data.suggestions.length > 0) {
            renderSuggestions(data.suggestions);
        }
    } catch {}
}

function renderSuggestions(suggestions) {
    const container = document.getElementById('search-suggestions');
    if (!container) return;

    container.innerHTML = suggestions.map(s => `
        <div class="suggestion-item" onclick="selectSuggestion('${escapeHtml(s)}')">
            <i data-lucide="search"></i>
            <span>${escapeHtml(s)}</span>
        </div>
    `).join('');
    container.classList.remove('hidden');
    lucide.createIcons({ nodes: [container] });
}

function selectSuggestion(query) {
    const input = document.getElementById('search-input');
    if (input) input.value = query;
    document.getElementById('search-clear')?.classList.remove('hidden');
    document.getElementById('search-suggestions')?.classList.add('hidden');
    performSearch(query);
}


// ============================================
// Track Card Rendering
// ============================================

function renderTrackCards(tracks, containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (!tracks || tracks.length === 0) {
        container.innerHTML = `<div class="empty-state-card"><p>No songs available</p></div>`;
        return;
    }

    container.innerHTML = tracks.map((track, i) => `
        <div class="track-card"
             data-video-id="${track.video_id}"
             onclick="playSingleTrack(${JSON.stringify(track).replace(/"/g, '&quot;')}, ${JSON.stringify(tracks).replace(/"/g, '&quot;')}, ${i})">
            <div class="track-card-art">
                <img src="${track.thumbnail || track.album_art || ''}"
                     alt=""
                     loading="lazy"
                     onerror="this.style.display='none'">
                <div class="track-card-play">
                    <i data-lucide="play"></i>
                </div>
            </div>
            <div class="track-card-title">${escapeHtml(track.track_name || track.title)}</div>
            <div class="track-card-artist" onclick="event.stopPropagation(); openArtistPage('${escapeHtml(track.artist)}')">${escapeHtml(track.artist)}</div>
        </div>
    `).join('');

    lucide.createIcons({ nodes: [container] });
}


// ============================================
// Play Helper Functions
// ============================================

function playTrackFromResults(index) {
    const track = AppState.searchResults[index];
    if (track && typeof Player !== 'undefined') {
        Player.setQueue(AppState.searchResults, index);
        Player.play(track);
    }
}

function playSingleTrack(track, fullList, index) {
    if (typeof Player !== 'undefined') {
        if (fullList && fullList.length > 0) {
            Player.setQueue(fullList, index);
        }
        Player.play(track);
    }
}

function playTrack(videoId, trackData) {
    if (typeof Player !== 'undefined') {
        Player.play(trackData || { video_id: videoId });
    }
}

function addToQueue(index) {
    const track = AppState.searchResults[index];
    if (track && typeof Player !== 'undefined') {
        Player.addToQueue(track);
        showToast(`Added "${track.track_name || track.title}" to queue`, 'success');
    }
}


// ============================================
// Utilities
// ============================================

function updateGreeting() {
    const hour = new Date().getHours();
    let greeting;
    if (hour < 12) greeting = 'morning';
    else if (hour < 17) greeting = 'afternoon';
    else greeting = 'evening';

    const el = document.getElementById('greeting-time');
    if (el) el.textContent = greeting;
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDuration(seconds) {
    if (!seconds || isNaN(seconds) || seconds <= 0) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}


// ============================================
// Initialization
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', () => {
            navigateTo(item.dataset.page);
        });
    });

    const searchInput = document.getElementById('search-input');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            const query = e.target.value;
            document.getElementById('search-clear')?.classList.toggle('hidden', !query);

            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => {
                fetchSuggestions(query);
            }, 250);
        });

        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                document.getElementById('search-suggestions')?.classList.add('hidden');
                performSearch(searchInput.value);
            }
        });

        document.addEventListener('click', (e) => {
            if (!e.target.closest('.search-header')) {
                document.getElementById('search-suggestions')?.classList.add('hidden');
            }
        });
    }

    document.getElementById('search-clear')?.addEventListener('click', () => {
        const input = document.getElementById('search-input');
        if (input) {
            input.value = '';
            input.focus();
        }
        document.getElementById('search-clear')?.classList.add('hidden');
        document.getElementById('search-suggestions')?.classList.add('hidden');
        document.getElementById('search-browse-tags')?.classList.remove('hidden');
        document.getElementById('search-results').innerHTML = `
            <div class="search-placeholder">
                <i data-lucide="disc-3"></i>
                <h2>Explore songs worldwide</h2>
                <p>Type any song name, movie, singer, or genre in any language</p>
            </div>
        `;
        lucide.createIcons({ nodes: [document.getElementById('search-results')] });
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        switch (e.key) {
            case ' ':
                e.preventDefault();
                if (typeof Player !== 'undefined') Player.togglePlay();
                break;
            case 'ArrowRight':
                if (typeof Player !== 'undefined') Player.seekRelative(10);
                break;
            case 'ArrowLeft':
                if (typeof Player !== 'undefined') Player.seekRelative(-10);
                break;
            case 'ArrowUp':
                e.preventDefault();
                if (typeof Player !== 'undefined') Player.adjustVolume(5);
                break;
            case 'ArrowDown':
                e.preventDefault();
                if (typeof Player !== 'undefined') Player.adjustVolume(-5);
                break;
            case '/':
                e.preventDefault();
                navigateTo('search');
                break;
        }
    });

    initHomeFeed();

    if (typeof Auth !== 'undefined') {
        Auth.init();
    }
});
