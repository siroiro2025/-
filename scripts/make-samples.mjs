import sharp from 'sharp';
import fs from 'fs';
import path from 'path';

const SAMPLES_DIR = './samples';

// Ensure samples directory exists
fs.mkdirSync(SAMPLES_DIR, { recursive: true });

// Define image specifications deterministically (no randomness)
const imageConfigs = [
  // Solid colors - varied sizes
  { name: 'red-solid-square', width: 1024, height: 1024, format: 'jpg', color: '#FF0000' },
  { name: 'blue-solid-landscape', width: 1600, height: 400, format: 'png', color: '#0000FF' },
  { name: 'green-solid-portrait', width: 400, height: 1600, format: 'webp', color: '#00FF00' },

  // Horizontal gradients
  { name: 'sunset-gradient-01', width: 1200, height: 600, format: 'jpg', gradient: ['#FF6B00', '#FFC300'], direction: 'horizontal' },
  { name: 'ocean-gradient-02', width: 800, height: 1000, format: 'png', gradient: ['#0077BE', '#00D4FF'], direction: 'horizontal' },
  { name: 'forest-gradient-03', width: 600, height: 900, format: 'webp', gradient: ['#134E5E', '#71B280'], direction: 'horizontal' },
  { name: 'coral-gradient-04', width: 1400, height: 500, format: 'jpg', gradient: ['#FF7E5F', '#FEB47B'], direction: 'horizontal' },
  { name: 'purple-gradient-05', width: 900, height: 700, format: 'png', gradient: ['#667EEA', '#764BA2'], direction: 'horizontal' },

  // Vertical gradients
  { name: 'lavender-gradient-06', width: 1600, height: 400, format: 'jpg', gradient: ['#E0B0FF', '#FFFFFF'], direction: 'vertical' },
  { name: 'midnight-gradient-07', width: 400, height: 1600, format: 'png', gradient: ['#0F0C29', '#302B63'], direction: 'vertical' },
  { name: 'sky-gradient-08', width: 1200, height: 800, format: 'webp', gradient: ['#4FACFE', '#00F2FE'], direction: 'vertical' },
  { name: 'flame-gradient-09', width: 1000, height: 600, format: 'png', gradient: ['#FA709A', '#FEE140'], direction: 'vertical' },

  // Circle patterns
  { name: 'blue-circles-01', width: 800, height: 800, format: 'png', pattern: 'circles', color1: '#3498DB', color2: '#FFFFFF' },
  { name: 'purple-circles-02', width: 600, height: 600, format: 'jpg', pattern: 'circles', color1: '#9B59B6', color2: '#ECF0F1' },
  { name: 'green-circles-03', width: 1024, height: 1024, format: 'webp', pattern: 'circles', color1: '#27AE60', color2: '#F4F6F7' },
  { name: 'orange-circles-04', width: 700, height: 700, format: 'png', pattern: 'circles', color1: '#E67E22', color2: '#FEF5E7' },

  // Stripe patterns
  { name: 'rainbow-stripes-01', width: 1200, height: 400, format: 'webp', pattern: 'stripes', color1: '#E74C3C', color2: '#F39C12' },
  { name: 'teal-stripes-02', width: 400, height: 1200, format: 'png', pattern: 'stripes', color1: '#16A085', color2: '#D5F4E6' },
  { name: 'red-stripes-03', width: 1100, height: 550, format: 'jpg', pattern: 'stripes', color1: '#C0392B', color2: '#FADBD8' },
  { name: 'blue-stripes-04', width: 650, height: 1300, format: 'webp', pattern: 'stripes', color1: '#2980B9', color2: '#D6EAF8' },

  // Checkerboard patterns
  { name: 'checkerboard-classic-01', width: 1024, height: 1024, format: 'jpg', pattern: 'checkerboard', color1: '#000000', color2: '#FFFFFF' },
  { name: 'checkerboard-color-02', width: 800, height: 800, format: 'png', pattern: 'checkerboard', color1: '#FF1493', color2: '#00CED1' },
  { name: 'checkerboard-green-03', width: 900, height: 900, format: 'webp', pattern: 'checkerboard', color1: '#2ECC71', color2: '#1C2833' },
  { name: 'checkerboard-gold-04', width: 700, height: 700, format: 'jpg', pattern: 'checkerboard', color1: '#F39C12', color2: '#34495E' },

  // Additional mixed sizes and formats
  { name: 'landscape-large-01', width: 1600, height: 400, format: 'jpg', gradient: ['#A8EDEA', '#FED6E3'], direction: 'horizontal' },
  { name: 'landscape-med-02', width: 1400, height: 600, format: 'png', pattern: 'circles', color1: '#667EEA', color2: '#764BA2' },
  { name: 'landscape-small-03', width: 1000, height: 450, format: 'webp', gradient: ['#FFB88C', '#A29BFE'], direction: 'vertical' },

  { name: 'portrait-large-01', width: 400, height: 1600, format: 'png', gradient: ['#4FACFE', '#00F2FE'], direction: 'vertical' },
  { name: 'portrait-med-02', width: 600, height: 1200, format: 'jpg', pattern: 'stripes', color1: '#FA709A', color2: '#FEE140' },
  { name: 'portrait-small-03', width: 450, height: 1000, format: 'webp', gradient: ['#00B894', '#55EFC4'], direction: 'horizontal' },

  { name: 'square-large-01', width: 1200, height: 1200, format: 'png', color: '#E8DAEF' },
  { name: 'square-med-02', width: 800, height: 800, format: 'jpg', gradient: ['#FDCB6E', '#E17055'], direction: 'horizontal' },
  { name: 'square-small-03', width: 512, height: 512, format: 'webp', pattern: 'checkerboard', color1: '#BDC3C7', color2: '#2C3E50' },

  // Additional small size variations
  { name: 'tiny-square-01', width: 400, height: 400, format: 'png', gradient: ['#FF6348', '#FFD93D'], direction: 'vertical' },
  { name: 'tiny-landscape-02', width: 600, height: 300, format: 'jpg', color: '#9B59B6' },
  { name: 'tiny-portrait-03', width: 300, height: 600, format: 'webp', gradient: ['#6C5CE7', '#00B894'], direction: 'horizontal' },
  { name: 'tiny-checkerboard-04', width: 500, height: 500, format: 'png', pattern: 'checkerboard', color1: '#FF1744', color2: '#F1F8E9' },
];

// Create SVG for gradient
function createGradientSVG(width, height, color1, color2, direction) {
  const isVertical = direction === 'vertical';
  const x1 = isVertical ? '0%' : '0%';
  const y1 = isVertical ? '0%' : '0%';
  const x2 = isVertical ? '0%' : '100%';
  const y2 = isVertical ? '100%' : '0%';

  return `<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="grad" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}">
        <stop offset="0%" stop-color="${color1}" />
        <stop offset="100%" stop-color="${color2}" />
      </linearGradient>
    </defs>
    <rect width="${width}" height="${height}" fill="url(#grad)" />
  </svg>`;
}

// Create SVG for patterns
function createPatternSVG(width, height, pattern, color1, color2) {
  if (pattern === 'circles') {
    const circles = [];
    const circleSize = 40;
    for (let y = 0; y < height; y += circleSize * 2) {
      for (let x = 0; x < width; x += circleSize * 2) {
        circles.push(`<circle cx="${x + circleSize}" cy="${y + circleSize}" r="${circleSize}" fill="${color1}" />`);
      }
    }
    return `<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
      <rect width="${width}" height="${height}" fill="${color2}" />
      ${circles.join('\n')}
    </svg>`;
  } else if (pattern === 'stripes') {
    const stripes = [];
    const stripeWidth = 20;
    for (let x = 0; x < width; x += stripeWidth * 2) {
      stripes.push(`<rect x="${x}" y="0" width="${stripeWidth}" height="${height}" fill="${color1}" />`);
    }
    return `<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
      <rect width="${width}" height="${height}" fill="${color2}" />
      ${stripes.join('\n')}
    </svg>`;
  } else if (pattern === 'checkerboard') {
    const squares = [];
    const squareSize = 32;
    for (let y = 0; y < height; y += squareSize) {
      for (let x = 0; x < width; x += squareSize) {
        const isEven = (Math.floor(x / squareSize) + Math.floor(y / squareSize)) % 2 === 0;
        const color = isEven ? color1 : color2;
        squares.push(`<rect x="${x}" y="${y}" width="${squareSize}" height="${squareSize}" fill="${color}" />`);
      }
    }
    return `<svg width="${width}" height="${height}" xmlns="http://www.w3.org/2000/svg">
      ${squares.join('\n')}
    </svg>`;
  }
}

// Generate all images
let generatedCount = 0;
const generatePromises = imageConfigs.map(async (config) => {
  try {
    let sharpInstance;

    if (config.color) {
      // Solid color
      sharpInstance = sharp({
        create: {
          width: config.width,
          height: config.height,
          channels: 3,
          background: config.color,
        },
      });
    } else if (config.gradient) {
      // Gradient
      const svg = createGradientSVG(config.width, config.height, config.gradient[0], config.gradient[1], config.direction);
      sharpInstance = sharp(Buffer.from(svg));
    } else if (config.pattern) {
      // Pattern
      const svg = createPatternSVG(config.width, config.height, config.pattern, config.color1, config.color2);
      sharpInstance = sharp(Buffer.from(svg));
    }

    const filename = `${config.name}.${config.format}`;
    const filepath = path.join(SAMPLES_DIR, filename);

    await sharpInstance
      .resize(config.width, config.height, { fit: 'cover' })
      .toFormat(config.format)
      .toFile(filepath);

    generatedCount++;
  } catch (error) {
    console.error(`Error generating ${config.name}:`, error.message);
  }
});

await Promise.all(generatePromises);

console.log(`✓ Generated ${generatedCount} sample images in ${SAMPLES_DIR}/`);
