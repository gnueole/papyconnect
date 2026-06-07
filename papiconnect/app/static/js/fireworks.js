// ─────────────────────────────────────────────────────────────────────────
// Canvas Fireworks Particle System (Coded by Éole & Antigravity)
// ─────────────────────────────────────────────────────────────────────────
let fireworksAnimId = null;
let fireworksCanvas = null;
let fireworksCtx = null;
let fireworksParticles = [];
let fireworksExplosions = [];

function startFireworks() {
  fireworksCanvas = document.getElementById('fireworksCanvas');
  if (!fireworksCanvas) return;
  fireworksCanvas.classList.remove('fireworks-hidden');
  fireworksCtx = fireworksCanvas.getContext('2d');
  
  resizeFireworksCanvas();
  window.addEventListener('resize', resizeFireworksCanvas);

  fireworksParticles = [];
  fireworksExplosions = [];
  
  // Spawn initial set
  for (let i = 0; i < 5; i++) {
    setTimeout(spawnFirework, i * 150);
  }

  animateFireworks();
}

function stopFireworks() {
  if (fireworksAnimId) {
    cancelAnimationFrame(fireworksAnimId);
    fireworksAnimId = null;
  }
  if (fireworksCanvas) {
    fireworksCanvas.classList.add('fireworks-hidden');
  }
  window.removeEventListener('resize', resizeFireworksCanvas);
}

function resizeFireworksCanvas() {
  if (fireworksCanvas) {
    fireworksCanvas.width = window.innerWidth;
    fireworksCanvas.height = window.innerHeight;
  }
}

class FireworkParticle {
  constructor(x, y, targetX, targetY, color) {
    this.x = x;
    this.y = y;
    this.targetX = targetX;
    this.targetY = targetY;
    this.color = color;
    this.speed = 3 + Math.random() * 4;
    this.angle = Math.atan2(targetY - y, targetX - x);
    this.distToTarget = Math.hypot(targetX - x, targetY - y);
    this.distTraveled = 0;
    this.coordinates = [];
    this.coordinateCount = 3;
    while (this.coordinateCount--) {
      this.coordinates.push([this.x, this.y]);
    }
  }

  update() {
    this.coordinates.pop();
    this.coordinates.unshift([this.x, this.y]);
    
    let vx = Math.cos(this.angle) * this.speed;
    let vy = Math.sin(this.angle) * this.speed;
    
    this.x += vx;
    this.y += vy;
    
    return Math.hypot(this.targetX - this.x, this.targetY - this.y) <= this.speed;
  }

  draw() {
    fireworksCtx.beginPath();
    fireworksCtx.moveTo(this.coordinates[this.coordinates.length - 1][0], this.coordinates[this.coordinates.length - 1][1]);
    fireworksCtx.lineTo(this.x, this.y);
    fireworksCtx.strokeStyle = this.color;
    fireworksCtx.lineWidth = 2.5;
    fireworksCtx.stroke();
  }
}

class ExplosionParticle {
  constructor(x, y, color) {
    this.x = x;
    this.y = y;
    this.color = color;
    this.angle = Math.random() * Math.PI * 2;
    this.speed = 2 + Math.random() * 8;
    this.friction = 0.94;
    this.gravity = 0.12;
    this.alpha = 1.0;
    this.decay = 0.008 + Math.random() * 0.012;
    this.coordinates = [];
    this.coordinateCount = 5;
    while (this.coordinateCount--) {
      this.coordinates.push([this.x, this.y]);
    }
  }

  update() {
    this.coordinates.pop();
    this.coordinates.unshift([this.x, this.y]);
    this.speed *= this.friction;
    this.x += Math.cos(this.angle) * this.speed;
    this.y += Math.sin(this.angle) * this.speed + this.gravity;
    this.alpha -= this.decay;
    return this.alpha <= this.decay;
  }

  draw() {
    fireworksCtx.beginPath();
    fireworksCtx.moveTo(this.coordinates[this.coordinates.length - 1][0], this.coordinates[this.coordinates.length - 1][1]);
    fireworksCtx.lineTo(this.x, this.y);
    fireworksCtx.strokeStyle = `rgba(${this.color}, ${this.alpha})`;
    fireworksCtx.lineWidth = 2.0;
    fireworksCtx.stroke();
  }
}

function hexToRgb(hex) {
  let result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result ? `${parseInt(result[1], 16)}, ${parseInt(result[2], 16)}, ${parseInt(result[3], 16)}` : '255, 255, 255';
}

function spawnFirework() {
  let x = Math.random() * window.innerWidth;
  let y = window.innerHeight;
  let targetX = Math.random() * window.innerWidth;
  let targetY = 100 + Math.random() * (window.innerHeight * 0.4);
  let colors = ['#e9a623', '#ff0055', '#00ffcc', '#ffcc00', '#ff00ff', '#33ccff', '#99ff33'];
  let color = colors[Math.floor(Math.random() * colors.length)];
  
  fireworksParticles.push(new FireworkParticle(x, y, targetX, targetY, color));
}

function createExplosion(x, y, colorHex) {
  let rgb = hexToRgb(colorHex);
  let count = 100 + Math.floor(Math.random() * 60); // Big big explosions!
  for (let i = 0; i < count; i++) {
    fireworksExplosions.push(new ExplosionParticle(x, y, rgb));
  }
}

function animateFireworks() {
  fireworksCtx.globalCompositeOperation = 'destination-out';
  fireworksCtx.fillStyle = 'rgba(0, 0, 0, 0.18)';
  fireworksCtx.fillRect(0, 0, fireworksCanvas.width, fireworksCanvas.height);
  fireworksCtx.globalCompositeOperation = 'lighter';

  for (let i = fireworksParticles.length - 1; i >= 0; i--) {
    let p = fireworksParticles[i];
    p.draw();
    if (p.update()) {
      createExplosion(p.targetX, p.targetY, p.color);
      fireworksParticles.splice(i, 1);
    }
  }

  for (let i = fireworksExplosions.length - 1; i >= 0; i--) {
    let ep = fireworksExplosions[i];
    ep.draw();
    if (ep.update()) {
      fireworksExplosions.splice(i, 1);
    }
  }

  if (Math.random() < 0.07) {
    spawnFirework();
  }

  fireworksAnimId = requestAnimationFrame(animateFireworks);
}
