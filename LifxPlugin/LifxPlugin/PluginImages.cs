namespace Loupedeck.LifxPlugin
{
    using System;

    internal static class PluginImages
    {
        public static readonly BitmapColor PurpleColor = new BitmapColor(0x82, 0x00, 0xFF);
        public static readonly BitmapColor BlackColor = BitmapColor.Black;
        public static readonly BitmapColor DullWhiteColor = new BitmapColor(200, 200, 200);

        public static BitmapImage CreateButtonImage(PluginImageSize imageSize, string text, BitmapColor? textColor = null, BitmapColor? bgColor = null)
        {
            if (imageSize == PluginImageSize.None)
            {
                return null;
            }

            var tc = textColor ?? PurpleColor;
            var bg = bgColor ?? BlackColor;

            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(bg);

                var fontSize = BitmapBuilder.GetDefaultFontSize(imageSize);
                var lineHeight = BitmapBuilder.GetDefaultLineHeight(imageSize);
                var spaceHeight = BitmapBuilder.GetDefaultSpaceHeight(imageSize);

                builder.DrawText(text, tc, fontSize, lineHeight, spaceHeight);

                return builder.ToImage();
            }
        }

        public static BitmapImage CreateBulbButtonImage(PluginImageSize imageSize, bool isGroup, BitmapColor? textColor = null, BitmapColor? bgColor = null, bool isDisabled = false)
        {
            if (imageSize == PluginImageSize.None)
            {
                return null;
            }

            var tc = textColor ?? PurpleColor;
            var bg = bgColor ?? BlackColor;

            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(bg);

                int w = builder.Width;
                int h = builder.Height;

                // Center the bulb icon in the middle of the button
                float centerX = w / 2f;
                float centerY = h / 2f;
                float bulbSize = Math.Min(w, h) * 0.65f;

                if (isGroup)
                {
                    DrawTwoBulbs(builder, centerX, centerY, bulbSize, tc, isDisabled);
                }
                else
                {
                    DrawBulb(builder, centerX, centerY, bulbSize, tc, isDisabled);
                }

                return builder.ToImage();
            }
        }

        public static BitmapColor ParseHexColor(string hex)
        {
            try
            {
                if (string.IsNullOrEmpty(hex)) return PurpleColor;
                if (hex.StartsWith("#")) hex = hex.Substring(1);
                if (hex.Length == 6)
                {
                    int r = Convert.ToInt32(hex.Substring(0, 2), 16);
                    int g = Convert.ToInt32(hex.Substring(2, 2), 16);
                    int b = Convert.ToInt32(hex.Substring(4, 2), 16);
                    return new BitmapColor(r, g, b);
                }
            }
            catch {}
            return PurpleColor;
        }

        public static BitmapImage CreateSceneButtonImage(PluginImageSize imageSize, System.Collections.Generic.List<string> colorsHex = null, BitmapColor? textColor = null, BitmapColor? bgColor = null)
        {
            if (imageSize == PluginImageSize.None) return null;

            var tc = textColor ?? PurpleColor;
            var bg = bgColor ?? BlackColor;

            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(bg);

                int w = builder.Width;
                int h = builder.Height;

                // Frame boundaries
                int padX = (int)(w * 0.15f);
                int padY = (int)(h * 0.18f);
                int frameW = w - 2 * padX;
                int frameH = h - 2 * padY;

                // Determine dynamic colors for scene parts based on scene status colors
                var frameColor = tc;
                var sunColor = new BitmapColor(255, 200, 50); // golden sun by default
                var m1Color = tc;
                var m2Color = tc;

                if (colorsHex != null && colorsHex.Count > 0)
                {
                    var parsedColors = new System.Collections.Generic.List<BitmapColor>();
                    foreach (var hex in colorsHex)
                    {
                        parsedColors.Add(ParseHexColor(hex));
                    }

                    if (parsedColors.Count == 1)
                    {
                        sunColor = parsedColors[0];
                        m1Color = parsedColors[0];
                        m2Color = parsedColors[0];
                    }
                    else if (parsedColors.Count == 2)
                    {
                        sunColor = parsedColors[0];
                        m1Color = parsedColors[1];
                        m2Color = parsedColors[1];
                    }
                    else if (parsedColors.Count >= 3)
                    {
                        sunColor = parsedColors[0];
                        m1Color = parsedColors[1];
                        m2Color = parsedColors[2];
                    }
                }

                // 1. Draw frame border
                builder.DrawRectangle(padX, padY, frameW, frameH, frameColor);
                builder.DrawRectangle(padX + 1, padY + 1, frameW - 2, frameH - 2, frameColor);

                // 2. Draw a sun inside the frame (top right quadrant)
                float sunX = padX + frameW * 0.7f;
                float sunY = padY + frameH * 0.3f;
                float sunRadius = frameH * 0.16f;
                builder.DrawCircle((int)sunX, (int)sunY, (int)sunRadius, sunColor);

                // 3. Draw mountains (lines)
                float m1StartX = padX + 2;
                float m1StartY = padY + frameH - 2;
                float m1PeakX = padX + frameW * 0.35f;
                float m1PeakY = padY + frameH * 0.45f;
                float m1EndX = padX + frameW * 0.7f;
                float m1EndY = padY + frameH - 2;

                builder.DrawLine(m1StartX, m1StartY, m1PeakX, m1PeakY, m1Color, 2f);
                builder.DrawLine(m1PeakX, m1PeakY, m1EndX, m1EndY, m1Color, 2f);

                float m2StartX = padX + frameW - 2;
                float m2StartY = padY + frameH - 2;
                float m2PeakX = padX + frameW * 0.65f;
                float m2PeakY = padY + frameH * 0.35f;
                float m2EndX = padX + frameW * 0.3f;
                float m2EndY = padY + frameH - 2;

                builder.DrawLine(m2StartX, m2StartY, m2PeakX, m2PeakY, m2Color, 2f);
                builder.DrawLine(m2PeakX, m2PeakY, m2EndX, m2EndY, m2Color, 2f);

                return builder.ToImage();
            }
        }

        private static void DrawBulb(BitmapBuilder builder, float x, float y, float size, BitmapColor color, bool isDisabled = false)
        {
            var drawColor = isDisabled ? new BitmapColor(100, 100, 100) : color;

            // Glass part
            float bulbRadius = size * 0.28f;
            float bulbCenterY = y - size * 0.08f;
            builder.DrawCircle((int)x, (int)bulbCenterY, (int)bulbRadius, drawColor);
            builder.DrawCircle((int)x, (int)bulbCenterY, (int)(bulbRadius - 0.7f), drawColor);
            builder.DrawCircle((int)x, (int)bulbCenterY, (int)(bulbRadius - 1.4f), drawColor);

            // Metal base
            float baseWidth = size * 0.20f;
            float baseHeight = size * 0.12f;
            float baseX = x - baseWidth / 2f;
            float baseY = bulbCenterY + bulbRadius - size * 0.04f;
            builder.DrawRectangle((int)baseX, (int)baseY, (int)baseWidth, (int)baseHeight, drawColor);
            builder.DrawRectangle((int)baseX + 1, (int)baseY + 1, (int)baseWidth - 2, (int)baseHeight - 2, drawColor);

            // Base threads
            builder.DrawLine(baseX, baseY + baseHeight * 0.33f, baseX + baseWidth, baseY + baseHeight * 0.33f, drawColor, 2.5f);
            builder.DrawLine(baseX + baseWidth * 0.2f, baseY + baseHeight * 0.66f, baseX + baseWidth * 0.8f, baseY + baseHeight * 0.66f, drawColor, 2.5f);

            // Filament
            float filY = bulbCenterY + bulbRadius * 0.2f;
            builder.DrawLine(x - bulbRadius * 0.3f, filY, x + bulbRadius * 0.3f, filY, drawColor, 2.5f);
            builder.DrawLine(x - bulbRadius * 0.3f, filY, x - bulbRadius * 0.1f, filY - bulbRadius * 0.3f, drawColor, 2.5f);
            builder.DrawLine(x + bulbRadius * 0.3f, filY, x + bulbRadius * 0.1f, filY - bulbRadius * 0.3f, drawColor, 2.5f);

            if (!isDisabled)
            {
                // Rays
                float rayLength = size * 0.08f;
                float startDist = bulbRadius + size * 0.04f;
                // Top
                builder.DrawLine(x, bulbCenterY - startDist, x, bulbCenterY - startDist - rayLength, drawColor, 3f);
                // Left & Right
                builder.DrawLine(x - startDist, bulbCenterY, x - startDist - rayLength, bulbCenterY, drawColor, 3f);
                builder.DrawLine(x + startDist, bulbCenterY, x + startDist + rayLength, bulbCenterY, drawColor, 3f);
                // Diagonals
                builder.DrawLine(x - startDist * 0.7f, bulbCenterY - startDist * 0.7f, x - (startDist + rayLength) * 0.7f, bulbCenterY - (rayLength + startDist) * 0.7f, drawColor, 3f);
                builder.DrawLine(x + startDist * 0.7f, bulbCenterY - startDist * 0.7f, x + (startDist + rayLength) * 0.7f, bulbCenterY - (rayLength + startDist) * 0.7f, drawColor, 3f);
            }
            else
            {
                // Draw diagonal slash across the bulb
                float slashSize = size * 0.35f;
                builder.DrawLine(x - slashSize, y - slashSize, x + slashSize, y + slashSize, new BitmapColor(180, 80, 80), 3f);
            }
        }

        private static void DrawTwoBulbs(BitmapBuilder builder, float x, float y, float size, BitmapColor color, bool isDisabled = false)
        {
            // Left bulb slightly lower and offset
            DrawBulb(builder, x - size * 0.18f, y + size * 0.04f, size * 0.75f, color, isDisabled);

            // Right bulb slightly higher and offset
            DrawBulb(builder, x + size * 0.18f, y - size * 0.04f, size * 0.75f, color, isDisabled);
        }

        private static void DrawLightString(BitmapBuilder builder, float x, float y, float size, BitmapColor tc, bool isDisabled = false)
        {
            // When active (purple bg, tc=Black): use white tape + white LEDs so coil is visible on purple
            // When inactive (black bg, tc=Purple): use purple tape + purple LEDs
            // When disabled: use gray
            var isActive = !isDisabled && tc == BlackColor;
            var ledColor = isDisabled ? new BitmapColor(80, 80, 80) : (isActive ? new BitmapColor(255, 255, 255) : PurpleColor);
            var tapeColor = isDisabled ? new BitmapColor(50, 50, 50) : (isActive ? new BitmapColor(200, 200, 200) : new BitmapColor(160, 100, 200));

            // Draw concentric partial circles (coiled tape)
            float r1 = size * 0.40f;
            float r2 = size * 0.27f;
            float r3 = size * 0.15f;

            // Draw outer tape segment
            builder.DrawArc((int)x, (int)y, (int)r1, 0f, 320f, tapeColor, 3f);
            // Draw mid tape segment
            builder.DrawArc((int)x, (int)y, (int)r2, 40f, 320f, tapeColor, 3f);
            // Draw inner tape segment
            builder.DrawArc((int)x, (int)y, (int)r3, 80f, 320f, tapeColor, 3f);

            // Spooled LEDs coordinates
            // Outer LEDs
            float[] outerAngles = { 45f, 135f, 225f, 300f };
            // Mid LEDs
            float[] midAngles = { 90f, 210f, 310f };
            // Inner LEDs
            float[] innerAngles = { 180f };

            // Helper to draw LED node
            Action<float, float> drawLed = (px, py) =>
            {
                builder.DrawCircle((int)px, (int)py, (int)(size * 0.05f), ledColor);
                if (!isDisabled)
                {
                    // Draw glow ring around each LED
                    builder.DrawCircle((int)px, (int)py, (int)(size * 0.08f), ledColor);
                }
            };

            // Draw outer LEDs
            foreach (var a in outerAngles)
            {
                float rad = a * (float)Math.PI / 180f;
                drawLed(x + r1 * (float)Math.Cos(rad), y + r1 * (float)Math.Sin(rad));
            }

            // Draw mid LEDs
            foreach (var a in midAngles)
            {
                float rad = a * (float)Math.PI / 180f;
                drawLed(x + r2 * (float)Math.Cos(rad), y + r2 * (float)Math.Sin(rad));
            }

            // Draw inner LEDs
            foreach (var a in innerAngles)
            {
                float rad = a * (float)Math.PI / 180f;
                drawLed(x + r3 * (float)Math.Cos(rad), y + r3 * (float)Math.Sin(rad));
            }

            if (isDisabled)
            {
                // Draw diagonal slash across the coil
                float slashSize = size * 0.45f;
                builder.DrawLine(x - slashSize, y - slashSize, x + slashSize, y + slashSize, new BitmapColor(180, 80, 80), 3f);
            }
        }

        private static void DrawOtherLight(BitmapBuilder builder, float x, float y, float size, BitmapColor tc, bool isDisabled = false)
        {
            var drawColor = isDisabled ? new BitmapColor(100, 100, 100) : tc;

            float squareSize = size * 0.35f;
            float offset = size * 0.22f;

            float[] px = new float[4] { x - offset, x + offset, x - offset, x + offset };
            float[] py = new float[4] { y - offset, y - offset, y + offset, y + offset };

            for (int i = 0; i < 4; i++)
            {
                int sx = (int)(px[i] - squareSize / 2f);
                int sy = (int)(py[i] - squareSize / 2f);

                builder.DrawRectangle(sx, sy, (int)squareSize, (int)squareSize, drawColor);
                builder.DrawRectangle(sx + 1, sy + 1, (int)squareSize - 2, (int)squareSize - 2, drawColor);

                if (!isDisabled)
                {
                    builder.DrawRectangle(sx + 2, sy + 2, (int)squareSize - 4, (int)squareSize - 4, drawColor);
                }
            }

            if (isDisabled)
            {
                // Draw diagonal slash across the matrix
                float slashSize = size * 0.45f;
                builder.DrawLine(x - slashSize, y - slashSize, x + slashSize, y + slashSize, new BitmapColor(180, 80, 80), 3f);
            }
        }

        public static BitmapImage CreateLightTypeButtonImage(PluginImageSize imageSize, string type, bool isGroup, BitmapColor? textColor = null, BitmapColor? bgColor = null, bool isDisabled = false)
        {
            if (imageSize == PluginImageSize.None)
            {
                return null;
            }

            var tc = textColor ?? PurpleColor;
            var bg = bgColor ?? BlackColor;

            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(bg);

                int w = builder.Width;
                int h = builder.Height;

                float centerX = w / 2f;
                float centerY = h / 2f;
                float size = Math.Min(w, h) * 0.65f;

                if (isGroup)
                {
                    DrawTwoBulbs(builder, centerX, centerY, size, tc, isDisabled);
                }
                else
                {
                    if (type == "string")
                    {
                        DrawLightString(builder, centerX, centerY, size, tc, isDisabled);
                    }
                    else if (type == "other")
                    {
                        DrawOtherLight(builder, centerX, centerY, size, tc, isDisabled);
                    }
                    else
                    {
                        DrawBulb(builder, centerX, centerY, size, tc, isDisabled);
                    }
                }

                return builder.ToImage();
            }
        }

        public static BitmapImage CreateColorWheelImage(PluginImageSize imageSize, string text = null, BitmapColor? bgColor = null)
        {
            if (imageSize == PluginImageSize.None)
            {
                return null;
            }

            var bg = bgColor ?? BlackColor;

            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(bg);

                int w = builder.Width;
                int h = builder.Height;

                int centerX = w / 2;
                int centerY = h / 2;
                int outerRadius = (int)(Math.Min(w, h) * 0.35); 
                int strokeWidth = (int)(Math.Min(w, h) * 0.11); 

                // Full 360-degree color wheel restored
                for (int i = 0; i < 36; i++)
                {
                    float startAngle = i * 10f;
                    float sweepAngle = 10.5f; 
                    double hue = i * 10.0;

                    if (BitmapColor.TryParseHslaColor(hue, 1.0, 0.5, 255, out var arcColor))
                    {
                        builder.DrawArc(centerX, centerY, outerRadius, startAngle, sweepAngle, arcColor, strokeWidth);
                    }
                }

                if (!string.IsNullOrEmpty(text))
                {
                    var tc = PurpleColor;
                    int fontSize = (int)(w * 0.13f); 
                    int lineHeight = (int)(fontSize * 1.2f);
                    int spaceHeight = (int)(fontSize * 0.3f);
                    
                    int boxW = (int)(outerRadius * 2 * 0.8f);
                    int boxH = (int)(outerRadius * 2 * 0.8f);
                    int boxX = centerX - boxW / 2;
                    int boxY = centerY - boxH / 2;

                    builder.DrawText(text, boxX, boxY, boxW, boxH, tc, fontSize, lineHeight, spaceHeight, "Brown Logitech Pan Light");
                }

                return builder.ToImage();
            }
        }

        public static BitmapImage CreateBrightnessGaugeImage(PluginImageSize imageSize, string text = null, BitmapColor? bgColor = null)
        {
            if (imageSize == PluginImageSize.None)
            {
                return null;
            }

            var bg = bgColor ?? BlackColor;

            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(bg);

                int w = builder.Width;
                int h = builder.Height;

                int centerX = w / 2;
                int centerY = h / 2;
                int outerRadius = (int)(Math.Min(w, h) * 0.35); 
                int strokeWidth = (int)(Math.Min(w, h) * 0.11); 

                // Draw 27 segments graduating from a visible base yellow (30%) to full gold/yellow (100%)
                for (int i = 0; i < 27; i++)
                {
                    float startAngle = 135f + i * 10f;
                    float sweepAngle = 10.5f; 
                    float t = 0.3f + 0.7f * (i / 26f); // color fraction starting at 30% for symmetry

                    int r = (int)(255 * t);
                    int g = (int)(220 * t);
                    int b = (int)(50 * t);
                    var arcColor = new BitmapColor(r, g, b);

                    builder.DrawArc(centerX, centerY, outerRadius, startAngle, sweepAngle, arcColor, strokeWidth);
                }

                if (!string.IsNullOrEmpty(text))
                {
                    var tc = PurpleColor;
                    int fontSize = (int)(w * 0.13f); 
                    int lineHeight = (int)(fontSize * 1.2f);
                    int spaceHeight = (int)(fontSize * 0.3f);
                    
                    int boxW = (int)(outerRadius * 2 * 0.8f);
                    int boxH = (int)(outerRadius * 2 * 0.8f);
                    int boxX = centerX - boxW / 2;
                    int boxY = centerY - boxH / 2;

                    builder.DrawText(text, boxX, boxY, boxW, boxH, tc, fontSize, lineHeight, spaceHeight, "Brown Logitech Pan Light");
                }

                return builder.ToImage();
            }
        }

        public static BitmapImage CreateWarmthWheelImage(PluginImageSize imageSize, BitmapColor? bgColor = null)
        {
            if (imageSize == PluginImageSize.None)
            {
                return null;
            }

            var bg = bgColor ?? BlackColor;

            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(bg);

                int w = builder.Width;
                int h = builder.Height;

                int centerX = w / 2;
                int centerY = h / 2;
                int outerRadius = (int)(Math.Min(w, h) * 0.35); 
                int strokeWidth = (int)(Math.Min(w, h) * 0.11); 

                // Smooth gradient around the 270-degree arc:
                // Inverted so it is warm orange (255, 100, 0) on the left (i=0) to cold blue (100, 180, 255) on the right (i=26)
                for (int i = 0; i < 27; i++)
                {
                    float startAngle = 135f + i * 10f;
                    float sweepAngle = 10.5f; 
                    
                    float t = (26 - i) / 26f;

                    int r = (int)(100 + (255 - 100) * t);
                    int g = (int)(180 + (100 - 180) * t);
                    int b = (int)(255 + (0 - 255) * t);
                    var arcColor = new BitmapColor(r, g, b);

                    builder.DrawArc(centerX, centerY, outerRadius, startAngle, sweepAngle, arcColor, strokeWidth);
                }

                return builder.ToImage();
            }
        }

        public static BitmapImage CreatePowerButtonImage(PluginImageSize imageSize, BitmapColor? textColor = null, BitmapColor? bgColor = null)
        {
            if (imageSize == PluginImageSize.None)
            {
                return null;
            }

            var tc = textColor ?? PurpleColor;
            var bg = bgColor ?? BlackColor;

            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(bg);

                int w = builder.Width;
                int h = builder.Height;

                int centerX = w / 2;
                int centerY = h / 2;
                int radius = (int)(Math.Min(w, h) * 0.28);
                int strokeWidth = (int)(Math.Min(w, h) * 0.06);
                if (strokeWidth < 1)
                {
                    strokeWidth = 1;
                }

                // Draw circle arc for the power symbol (from 300 degrees to 240 degrees, leaving the top open)
                builder.DrawArc(centerX, centerY, radius, 300f, 300f, tc, (float)strokeWidth);

                // Draw vertical line from center top downwards
                int lineStartY = centerY - (int)(radius * 1.2);
                int lineEndY = centerY;
                builder.DrawLine((float)centerX, (float)lineStartY, (float)centerX, (float)lineEndY, tc, (float)strokeWidth);

                return builder.ToImage();
            }
        }

        public static BitmapImage CreateResetColorImage(PluginImageSize imageSize)
        {
            if (imageSize == PluginImageSize.None) return null;

            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(BlackColor);

                int w = builder.Width;
                int h = builder.Height;

                int centerX = w / 2;
                int centerY = h / 2;

                // 1. Draw a thin, nice color wheel arc on the outer border
                int colorWheelRadius = (int)(Math.Min(w, h) * 0.40);
                int colorWheelStroke = (int)(Math.Min(w, h) * 0.05);
                if (colorWheelStroke < 1)
                {
                    colorWheelStroke = 1;
                }

                for (int i = 0; i < 36; i++)
                {
                    float startAngle = i * 10f;
                    float sweepAngle = 10.5f;
                    double hue = i * 10.0;
                    if (BitmapColor.TryParseHslaColor(hue, 1.0, 0.5, 255, out var arcColor))
                    {
                        builder.DrawArc(centerX, centerY, colorWheelRadius, startAngle, sweepAngle, arcColor, colorWheelStroke);
                    }
                }

                // 2. Draw a white bulb in the center
                float bulbSize = Math.Min(w, h) * 0.40f;
                DrawBulb(builder, centerX, centerY, bulbSize, new BitmapColor(255, 255, 255));

                // 3. Draw a circular reset/undo arrow in white around the bulb, but inside the color wheel
                int resetRadius = (int)(Math.Min(w, h) * 0.28);
                int resetStroke = (int)(Math.Min(w, h) * 0.05);
                if (resetStroke < 1)
                {
                    resetStroke = 1;
                }

                var resetColor = new BitmapColor(240, 240, 240);
                builder.DrawArc(centerX, centerY, resetRadius, -190f, 260f, resetColor, (float)resetStroke);

                // Arrowhead at top-right
                builder.DrawLine(centerX + 2, centerY - resetRadius, centerX + 8, centerY - resetRadius, resetColor, (float)resetStroke);
                builder.DrawLine(centerX + 8, centerY - resetRadius, centerX + 8, centerY - resetRadius + 6, resetColor, (float)resetStroke);

                return builder.ToImage();
            }
        }

        public static BitmapImage CreateBreatheEffectImage(PluginImageSize imageSize, BitmapColor? color = null)
        {
            if (imageSize == PluginImageSize.None) return null;
            var c = color ?? new BitmapColor(255, 80, 200); // pinkish/magenta default
            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(BlackColor);
                float cx = builder.Width / 2f;
                float cy = builder.Height / 2f;
                float baseR = builder.Width * 0.15f;
                // Inner solid circle
                builder.DrawCircle((int)cx, (int)cy, (int)baseR, c);
                // Outer ring 1
                builder.DrawArc((int)cx, (int)cy, (int)(baseR + builder.Width * 0.12f), 0f, 360f, c, 2.5f);
                // Outer ring 2
                builder.DrawArc((int)cx, (int)cy, (int)(baseR + builder.Width * 0.24f), 0f, 360f, c, 1.0f);
                return builder.ToImage();
            }
        }

        public static BitmapImage CreateMoveEffectImage(PluginImageSize imageSize)
        {
            if (imageSize == PluginImageSize.None) return null;
            var c = new BitmapColor(0, 180, 255); // vibrant cyan
            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(BlackColor);
                float w = builder.Width;
                float h = builder.Height;
                float y1 = h * 0.35f;
                float y2 = h * 0.5f;
                float y3 = h * 0.65f;
                float margin = w * 0.2f;

                // 3 horizontal tracks
                builder.DrawLine(margin, y1, w - margin, y1, c, 3f);
                builder.DrawLine(margin, y2, w - margin, y2, c, 3f);
                builder.DrawLine(margin, y3, w - margin, y3, c, 3f);

                // Chevron symbols pointing right
                builder.DrawLine(w * 0.45f, y1 - 5, w * 0.55f, y1, c, 3f);
                builder.DrawLine(w * 0.55f, y1, w * 0.45f, y1 + 5, c, 3f);

                builder.DrawLine(w * 0.6f, y2 - 5, w * 0.7f, y2, c, 3f);
                builder.DrawLine(w * 0.7f, y2, w * 0.6f, y2 + 5, c, 3f);

                builder.DrawLine(w * 0.3f, y3 - 5, w * 0.4f, y3, c, 3f);
                builder.DrawLine(w * 0.4f, y3, w * 0.3f, y3 + 5, c, 3f);

                return builder.ToImage();
            }
        }

        public static BitmapImage CreateMorphEffectImage(PluginImageSize imageSize)
        {
            if (imageSize == PluginImageSize.None) return null;
            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(BlackColor);
                float w = builder.Width;
                float h = builder.Height;
                float r = w * 0.18f;
                float cx = w / 2f;
                float cy = h / 2f;

                // Overlapping circles representing morphing colors
                builder.DrawCircle((int)cx, (int)(cy - r * 0.6f), (int)r, new BitmapColor(255, 50, 150)); // pink
                builder.DrawCircle((int)(cx - r * 0.6f), (int)(cy + r * 0.4f), (int)r, new BitmapColor(50, 150, 255)); // cyan/blue
                builder.DrawCircle((int)(cx + r * 0.6f), (int)(cy + r * 0.4f), (int)r, new BitmapColor(255, 200, 50)); // yellow

                return builder.ToImage();
            }
        }

        public static BitmapImage CreateFlameEffectImage(PluginImageSize imageSize)
        {
            if (imageSize == PluginImageSize.None) return null;
            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(BlackColor);
                float w = builder.Width;
                float h = builder.Height;
                float cx = w / 2f;
                float cy = h * 0.55f;

                // Stack of circles forming a glowing flame
                builder.DrawCircle((int)cx, (int)cy, (int)(w * 0.22f), new BitmapColor(255, 60, 0)); // outer red-orange
                builder.DrawCircle((int)cx, (int)(cy - w * 0.08f), (int)(w * 0.16f), new BitmapColor(255, 160, 0)); // orange-yellow
                builder.DrawCircle((int)cx, (int)(cy - w * 0.16f), (int)(w * 0.10f), new BitmapColor(255, 230, 0)); // yellow
                builder.DrawCircle((int)cx, (int)(cy - w * 0.24f), (int)(w * 0.05f), new BitmapColor(255, 255, 200)); // white/yellow tip

                return builder.ToImage();
            }
        }

        public static BitmapImage CreatePulseEffectImage(PluginImageSize imageSize, BitmapColor? color = null)
        {
            if (imageSize == PluginImageSize.None) return null;
            var c = color ?? PurpleColor;
            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(BlackColor);
                float w = builder.Width;
                float h = builder.Height;
                float cx = w / 2f;
                float cy = h / 2f;
                float margin = w * 0.15f;

                builder.DrawLine(margin, cy, cx - w * 0.15f, cy, c, 3f);
                builder.DrawLine(cx - w * 0.15f, cy, cx - w * 0.08f, cy + h * 0.08f, c, 3f);
                builder.DrawLine(cx - w * 0.08f, cy + h * 0.08f, cx, cy - h * 0.35f, c, 3f);
                builder.DrawLine(cx, cy - h * 0.35f, cx + w * 0.08f, cy + h * 0.25f, c, 3f);
                builder.DrawLine(cx + w * 0.08f, cy + h * 0.25f, cx + w * 0.15f, cy, c, 3f);
                builder.DrawLine(cx + w * 0.15f, cy, w - margin, cy, c, 3f);

                return builder.ToImage();
            }
        }

        public static BitmapImage CreateCloudsEffectImage(PluginImageSize imageSize)
        {
            if (imageSize == PluginImageSize.None) return null;
            var c = new BitmapColor(180, 220, 255); // soft cloud blue
            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(BlackColor);
                float w = builder.Width;
                float h = builder.Height;
                float cx = w / 2f;
                float cy = h / 2f;

                // 3 overlapping circles
                builder.DrawCircle((int)cx, (int)(cy - 4), (int)(w * 0.18f), c); // top
                builder.DrawCircle((int)(cx - 14), (int)(cy + 6), (int)(w * 0.13f), c); // left
                builder.DrawCircle((int)(cx + 14), (int)(cy + 6), (int)(w * 0.13f), c); // right

                // flat base line
                builder.DrawLine(cx - 24, cy + 16, cx + 24, cy + 16, c, 3f);

                return builder.ToImage();
            }
        }

        public static BitmapImage CreateSunriseEffectImage(PluginImageSize imageSize)
        {
            if (imageSize == PluginImageSize.None) return null;
            var c = new BitmapColor(255, 210, 0); // gold
            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(BlackColor);
                float w = builder.Width;
                float h = builder.Height;
                float cx = w / 2f;
                float horizonY = h * 0.65f;

                // Horizon line
                builder.DrawLine(w * 0.15f, horizonY, w * 0.85f, horizonY, c, 2.5f);
                // Rising Sun half-circle (top half)
                builder.DrawArc((int)cx, (int)horizonY, (int)(w * 0.2f), 180f, 180f, c, 3f);

                // Rays
                builder.DrawLine(cx - 22, horizonY - 8, cx - 32, horizonY - 14, c, 2.5f);
                builder.DrawLine(cx - 15, horizonY - 18, cx - 22, horizonY - 28, c, 2.5f);
                builder.DrawLine(cx, horizonY - 22, cx, horizonY - 34, c, 2.5f);
                builder.DrawLine(cx + 15, horizonY - 18, cx + 22, horizonY - 28, c, 2.5f);
                builder.DrawLine(cx + 22, horizonY - 8, cx + 32, horizonY - 14, c, 2.5f);

                // Up arrow indicating "rise"
                float arrowY = h * 0.2f;
                builder.DrawLine(cx, arrowY + 12, cx, arrowY, c, 2.5f);
                builder.DrawLine(cx - 4, arrowY + 4, cx, arrowY, c, 2.5f);
                builder.DrawLine(cx + 4, arrowY + 4, cx, arrowY, c, 2.5f);

                return builder.ToImage();
            }
        }

        public static BitmapImage CreateSunsetEffectImage(PluginImageSize imageSize)
        {
            if (imageSize == PluginImageSize.None) return null;
            var c = new BitmapColor(255, 90, 0); // orange-red
            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(BlackColor);
                float w = builder.Width;
                float h = builder.Height;
                float cx = w / 2f;
                float horizonY = h * 0.65f;

                // Horizon line
                builder.DrawLine(w * 0.15f, horizonY, w * 0.85f, horizonY, c, 2.5f);
                // Sunset half-circle (sinking)
                builder.DrawArc((int)cx, (int)horizonY, (int)(w * 0.2f), 180f, 180f, c, 3f);

                // Fewer Rays
                builder.DrawLine(cx - 20, horizonY - 5, cx - 28, horizonY - 10, c, 2.5f);
                builder.DrawLine(cx, horizonY - 20, cx, horizonY - 28, c, 2.5f);
                builder.DrawLine(cx + 20, horizonY - 5, cx + 28, horizonY - 10, c, 2.5f);

                // Down arrow indicating "set"
                float arrowY = h * 0.2f;
                builder.DrawLine(cx, arrowY, cx, arrowY + 12, c, 2.5f);
                builder.DrawLine(cx - 4, arrowY + 8, cx, arrowY + 12, c, 2.5f);
                builder.DrawLine(cx + 4, arrowY + 8, cx, arrowY + 12, c, 2.5f);

                return builder.ToImage();
            }
        }

        public static BitmapImage CreateEffectsOffImage(PluginImageSize imageSize)
        {
            if (imageSize == PluginImageSize.None) return null;
            var c = new BitmapColor(255, 50, 50); // vibrant red
            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(BlackColor);
                float cx = builder.Width / 2f;
                float cy = builder.Height / 2f;
                float r = builder.Width * 0.25f;

                // Stop circle with diagonal slash
                builder.DrawArc((int)cx, (int)cy, (int)r, 0f, 360f, c, 4.0f);
                builder.DrawLine(cx - r * 0.707f, cy - r * 0.707f, cx + r * 0.707f, cy + r * 0.707f, c, 4.0f);

                return builder.ToImage();
            }
        }

        public static BitmapImage CreateCycleEffectImage(PluginImageSize imageSize)
        {
            if (imageSize == PluginImageSize.None) return null;
            var c = new BitmapColor(180, 50, 255); // vibrant violet
            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(BlackColor);
                float cx = builder.Width / 2f;
                float cy = builder.Height / 2f;
                float r = builder.Width * 0.26f;

                // Circular arc
                builder.DrawArc((int)cx, (int)cy, (int)r, -190f, 260f, c, 3.0f);

                // Arrowhead at top-right
                builder.DrawLine(cx + 2, cy - r, cx + 8, cy - r, c, 3.0f);
                builder.DrawLine(cx + 8, cy - r, cx + 8, cy - r + 6, c, 3.0f);

                return builder.ToImage();
            }
        }

        public static BitmapImage CreateMovieModeImage(PluginImageSize imageSize, BitmapColor? textColor = null, BitmapColor? bgColor = null)
        {
            if (imageSize == PluginImageSize.None) return null;

            var tc = textColor ?? PurpleColor;
            var bg = bgColor ?? BlackColor;

            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(bg);

                int w = builder.Width;
                int h = builder.Height;

                float cx = w / 2f;
                float cy = h / 2f;

                // 1. Draw TV frame (rectangle)
                float tvW = w * 0.65f;
                float tvH = h * 0.45f;
                float tvX = cx - tvW / 2f;
                float tvY = cy - tvH / 2f - h * 0.05f;

                builder.DrawRectangle((int)tvX, (int)tvY, (int)tvW, (int)tvH, tc);
                builder.DrawRectangle((int)tvX + 1, (int)tvY + 1, (int)tvW - 2, (int)tvH - 2, tc);

                // TV stand / base
                float standW = w * 0.20f;
                float standH = h * 0.06f;
                float standX = cx - standW / 2f;
                float standY = tvY + tvH;
                builder.DrawLine(cx, standY, cx, standY + standH, tc, 2f);
                builder.DrawLine(cx - standW / 2f, standY + standH, cx + standW / 2f, standY + standH, tc, 2f);

                // 2. Draw play symbol (triangle) in the center of TV screen
                float triSize = tvH * 0.35f;
                float triX1 = cx - triSize * 0.4f;
                float triY1 = cy - triSize * 0.5f - h * 0.05f;
                float triX2 = cx - triSize * 0.4f;
                float triY2 = cy + triSize * 0.5f - h * 0.05f;
                float triX3 = cx + triSize * 0.6f;
                float triY3 = cy - h * 0.05f;

                builder.DrawLine(triX1, triY1, triX2, triY2, tc, 2f);
                builder.DrawLine(triX2, triY2, triX3, triY3, tc, 2f);
                builder.DrawLine(triX3, triY3, triX1, triY1, tc, 2f);

                // 3. Draw "MOVIE" text at the bottom
                var fontSize = (int)(w * 0.12f);
                var lineHeight = (int)(fontSize * 1.2f);
                var spaceHeight = (int)(fontSize * 0.3f);
                builder.DrawText("MOVIE", 0, (int)(h * 0.72f), w, (int)(h * 0.25f), tc, fontSize, lineHeight, spaceHeight);

                return builder.ToImage();
            }
        }
    }
}
