import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'THẮNG MIA · Web Studio',
  description: 'Điều phối 42 brief mỗi ngày cho 3 AI, không cần API AI.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="vi"><body>{children}</body></html>;
}
