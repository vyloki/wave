/**
 * Wave — Audio Visualizer
 * Canvas-based frequency visualization with iOS-safe background audio preservation.
 * Avoids Web Audio createMediaElementSource hijacking on iOS/Safari so audio continues
 * playing seamlessly on lock screen and in background.
 */

const Visualizer = {
    canvas: null,
    ctx: null,
    audioContext: null,
    analyser: null,
    sourceNode: null,
    dataArray: null,
    isActive: false,
    animationId: null,
    connected: false,
    isIOS: false,
    simulatedPhase: 0,

    barCount: 48,
    barGap: 3,
    smoothing: 0.82,

    init() {
        this.canvas = document.getElementById('visualizer-canvas');
        if (!this.canvas) return;

        this.ctx = this.canvas.getContext('2d');
        this.resizeCanvas();

        this.isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|mobile/i.test(navigator.userAgent) || 
                        (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1) ||
                        window.matchMedia('(pointer: coarse)').matches ||
                        window.navigator.standalone === true ||
                        window.matchMedia('(display-mode: standalone)').matches;

        window.addEventListener('resize', () => this.resizeCanvas());
    },

    resizeCanvas() {
        if (!this.canvas) return;
        this.canvas.width = this.canvas.offsetWidth * window.devicePixelRatio;
        this.canvas.height = this.canvas.offsetHeight * window.devicePixelRatio;
        this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    },

    connectToPlayer() {
        // On mobile / Safari / PWA, connecting createMediaElementSource forces audio through Web Audio
        // which mobile operating systems automatically pause when screen is locked or app is backgrounded.
        // We use procedural audio-reactive visualization on mobile to preserve 100% native background audio!
        if (this.isMobile) {
            this.connected = true;
            this.start();
            return;
        }

        if (this.connected || !Player?.audio) return;

        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            this.analyser.smoothingTimeConstant = this.smoothing;

            this.sourceNode = this.audioContext.createMediaElementSource(Player.audio);
            this.sourceNode.connect(this.analyser);
            this.analyser.connect(this.audioContext.destination);

            this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
            this.connected = true;
            this.start();
        } catch (error) {
            console.debug('Visualizer audio context init (falling back to simulated mode):', error);
            this.isMobile = true; // Fallback to simulated
            this.connected = true;
            this.start();
        }
    },

    start() {
        if (this.isActive) return;
        this.isActive = true;
        this.animate();
    },

    stop() {
        this.isActive = false;
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
        if (this.ctx && this.canvas) {
            this.ctx.clearRect(0, 0, this.canvas.offsetWidth, this.canvas.offsetHeight);
        }
    },

    animate() {
        if (!this.isActive) return;
        this.animationId = requestAnimationFrame(() => this.animate());
        this.draw();
    },

    draw() {
        if (!this.ctx || !this.canvas) return;

        const width = this.canvas.offsetWidth;
        const height = this.canvas.offsetHeight;
        this.ctx.clearRect(0, 0, width, height);

        if (!Player || !Player.isPlaying) return;

        const totalBarWidth = (width - (this.barCount - 1) * this.barGap) / this.barCount;
        const barWidth = Math.max(3, totalBarWidth);

        if (!this.isMobile && this.analyser && this.dataArray) {
            this.analyser.getByteFrequencyData(this.dataArray);

            for (let i = 0; i < this.barCount; i++) {
                const dataIndex = Math.floor((i / this.barCount) * this.dataArray.length * 0.65);
                const value = this.dataArray[dataIndex] || 0;
                const barHeight = Math.max(3, (value / 255) * height * 0.85);

                const x = i * (barWidth + this.barGap);
                const y = height - barHeight;

                const gradient = this.ctx.createLinearGradient(x, height, x, y);
                gradient.addColorStop(0, 'rgba(196, 168, 130, 0.2)');
                gradient.addColorStop(0.5, 'rgba(196, 168, 130, 0.6)');
                gradient.addColorStop(1, 'rgba(168, 139, 101, 0.9)');

                this.ctx.fillStyle = gradient;
                this.ctx.beginPath();
                this.ctx.roundRect(x, y, barWidth, barHeight, [3, 3, 0, 0]);
                this.ctx.fill();
            }
        } else {
            // Simulated audio-reactive procedural wave (iOS & fallback safe)
            this.simulatedPhase += 0.05;
            for (let i = 0; i < this.barCount; i++) {
                const wave1 = Math.sin(this.simulatedPhase + i * 0.18);
                const wave2 = Math.cos(this.simulatedPhase * 0.7 + i * 0.25);
                const wave3 = Math.sin(this.simulatedPhase * 1.3 - i * 0.12);
                const combined = Math.abs(wave1 * 0.5 + wave2 * 0.3 + wave3 * 0.2);
                const barHeight = Math.max(4, combined * height * 0.75);

                const x = i * (barWidth + this.barGap);
                const y = height - barHeight;

                const gradient = this.ctx.createLinearGradient(x, height, x, y);
                gradient.addColorStop(0, 'rgba(196, 168, 130, 0.2)');
                gradient.addColorStop(0.5, 'rgba(196, 168, 130, 0.6)');
                gradient.addColorStop(1, 'rgba(168, 139, 101, 0.9)');

                this.ctx.fillStyle = gradient;
                this.ctx.beginPath();
                this.ctx.roundRect(x, y, barWidth, barHeight, [3, 3, 0, 0]);
                this.ctx.fill();
            }
        }
    },
};

document.addEventListener('DOMContentLoaded', () => {
    Visualizer.init();

    if (Player?.audio) {
        Player.audio.addEventListener('play', () => {
            if (!Visualizer.connected) {
                Visualizer.connectToPlayer();
            } else {
                Visualizer.start();
            }
        });
        Player.audio.addEventListener('pause', () => {
            Visualizer.stop();
        });
    }
});
