import "./globals.css";

export const metadata = { title: "Rain ERP", description: "跨境电商 ERP" };

export default function RootLayout({children}:{children:React.ReactNode}) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
