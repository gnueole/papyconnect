namespace Loupedeck.PapyConnectPlugin
{
    using System;

    internal static class PluginImages
    {
        public static readonly BitmapColor PurpleColor = new BitmapColor(0x82, 0x00, 0xFF);
        public static readonly BitmapColor BlackColor = BitmapColor.Black;

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

                int w = builder.Width;
                int h = builder.Height;

                // Subtle premium double-border
                builder.DrawRectangle(0, 0, w, h, tc);
                builder.DrawRectangle(1, 1, w - 2, h - 2, tc);

                var fontSize = (int)(w * 0.14f);
                var lineHeight = (int)(fontSize * 1.25f);
                var spaceHeight = (int)(fontSize * 0.3f);

                builder.DrawText(text, 2, 2, w - 4, h - 4, tc, fontSize, lineHeight, spaceHeight);

                return builder.ToImage();
            }
        }

        public static BitmapImage CreateAppButtonImage(PluginImageSize imageSize, string appId)
        {
            if (imageSize == PluginImageSize.None)
            {
                return null;
            }

            using (var builder = new BitmapBuilder(imageSize))
            {
                builder.Clear(BlackColor);

                int w = builder.Width;
                int h = builder.Height;

                // Accent colors
                BitmapColor accentColor;
                if (appId == "netflix")
                {
                    accentColor = new BitmapColor(0xE5, 0x09, 0x14); // Netflix Red
                }
                else if (appId == "disney_plus")
                {
                    accentColor = new BitmapColor(0x00, 0x63, 0xE5); // Disney Blue
                }
                else if (appId == "amazon")
                {
                    accentColor = new BitmapColor(0x00, 0xA8, 0xE8); // Amazon Blue
                }
                else // youtube
                {
                    accentColor = new BitmapColor(0xFF, 0x00, 0x00); // YouTube Red
                }

                // Premium double-border
                builder.DrawRectangle(0, 0, w, h, accentColor);
                builder.DrawRectangle(1, 1, w - 2, h - 2, accentColor);

                // Draw icon graphics
                if (appId == "netflix")
                {
                    // Bold N in red
                    float leftX = w * 0.32f;
                    float rightX = w * 0.68f;
                    float topY = h * 0.22f;
                    float bottomY = h * 0.78f;
                    float thick = w * 0.13f;

                    // Left vertical ribbon
                    builder.DrawLine(leftX, topY, leftX, bottomY, accentColor, thick);
                    // Right vertical ribbon
                    builder.DrawLine(rightX, topY, rightX, bottomY, accentColor, thick);
                    // Diagonal ribbon (drawn on top)
                    builder.DrawLine(leftX, topY, rightX, bottomY, accentColor, thick);
                }
                else if (appId == "disney_plus")
                {
                    // 3 circles in blue that remind mickey
                    int centerX = w / 2;
                    int centerY = h / 2 + (int)(h * 0.05f);
                    int headRadius = (int)(w * 0.22f);
                    int earRadius = (int)(w * 0.13f);
                    int earOffset = (int)(w * 0.19f);

                    // Fill Head (concentric circles)
                    for (int r = 0; r <= headRadius; r++)
                    {
                        builder.DrawCircle(centerX, centerY, r, accentColor);
                    }
                    // Fill Left Ear
                    for (int r = 0; r <= earRadius; r++)
                    {
                        builder.DrawCircle(centerX - earOffset, centerY - earOffset, r, accentColor);
                    }
                    // Fill Right Ear
                    for (int r = 0; r <= earRadius; r++)
                    {
                        builder.DrawCircle(centerX + earOffset, centerY - earOffset, r, accentColor);
                    }
                }
                else if (appId == "amazon")
                {
                    // Bold A in blue
                    float topX = w * 0.5f;
                    float bottomY = h * 0.78f;
                    float thick = w * 0.12f;

                    // Left leg
                    builder.DrawLine(topX, h * 0.22f, w * 0.28f, bottomY, accentColor, thick);
                    // Right leg
                    builder.DrawLine(topX, h * 0.22f, w * 0.72f, bottomY, accentColor, thick);
                    // Crossbar
                    builder.DrawLine(w * 0.38f, h * 0.58f, w * 0.62f, h * 0.58f, accentColor, thick - 1f);
                }
                else if (appId == "youtube")
                {
                    // YouTube icon (Red rectangle with white play triangle)
                    int rectW = (int)(w * 0.62f);
                    int rectH = (int)(h * 0.44f);
                    int rectX = (w - rectW) / 2;
                    int rectY = (h - rectH) / 2;

                    // Fill Red Rounded Rectangle (using horizontal lines)
                    for (int y = rectY; y < rectY + rectH; y++)
                    {
                        builder.DrawLine(rectX, y, rectX + rectW, y, accentColor, 1f);
                    }

                    // White play triangle in center pointing right
                    var white = new BitmapColor(255, 255, 255);
                    int triStartX = w / 2 - (int)(w * 0.08f);
                    int triEndX = w / 2 + (int)(w * 0.11f);
                    int triCenterY = h / 2;
                    int triHalfHeight = (int)(h * 0.11f);

                    for (int x = triStartX; x <= triEndX; x++)
                    {
                        int dy = triHalfHeight - (x - triStartX) * triHalfHeight / (triEndX - triStartX + 1);
                        builder.DrawLine(x, triCenterY - dy, x, triCenterY + dy, white, 1f);
                    }
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
    }
}
