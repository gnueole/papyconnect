namespace Loupedeck.EoleN8NPlugin
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
