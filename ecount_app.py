import sqlite3
from datetime import datetime

class EcountERPDatabase:
    def __init__(self, db_name="/workspace/scratch/ecount_erp.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()
        self.seed_coa()

    def create_tables(self):
        """Membuat seluruh tabel basis data berdasarkan ERD ECOUNT ERP"""
        
        # 1. Master Pelanggan & Pemasok
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS pelanggan (
                id_pelanggan TEXT PRIMARY KEY,
                nama_pelanggan TEXT NOT NULL,
                telepon TEXT,
                alamat TEXT
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS pemasok (
                id_pemasok TEXT PRIMARY KEY,
                nama_pemasok TEXT NOT NULL,
                telepon TEXT,
                alamat TEXT
            )
        ''')

        # 2. Master Barang / Stok
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS barang (
                kode_barang TEXT PRIMARY KEY,
                nama_barang TEXT NOT NULL,
                harga_beli REAL NOT NULL,
                harga_jual REAL NOT NULL,
                stok INTEGER DEFAULT 0
            )
        ''')

        # 3. Master Bagan Akun (CoA)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS coa (
                kode_akun TEXT PRIMARY KEY,
                nama_akun TEXT NOT NULL,
                kategori TEXT NOT NULL -- Pemasukan, Pengeluaran, Aktiva, Kewajiban
            )
        ''')

        # 4. Transaksi Penjualan & Detail
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS penjualan (
                no_invoice TEXT PRIMARY KEY,
                tanggal TEXT NOT NULL,
                id_pelanggan TEXT,
                total_penjualan REAL NOT NULL,
                FOREIGN KEY (id_pelanggan) REFERENCES pelanggan (id_pelanggan)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS detail_penjualan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                no_invoice TEXT,
                kode_barang TEXT,
                jumlah INTEGER NOT NULL,
                subtotal REAL NOT NULL,
                FOREIGN KEY (no_invoice) REFERENCES penjualan (no_invoice),
                FOREIGN KEY (kode_barang) REFERENCES barang (kode_barang)
            )
        ''')

        # 5. Transaksi Pembelian & Detail
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS pembelian (
                no_po TEXT PRIMARY KEY,
                tanggal TEXT NOT NULL,
                id_pemasok TEXT,
                total_pembelian REAL NOT NULL,
                FOREIGN KEY (id_pemasok) REFERENCES pemasok (id_pemasok)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS detail_pembelian (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                no_po TEXT,
                kode_barang TEXT,
                jumlah INTEGER NOT NULL,
                subtotal REAL NOT NULL,
                FOREIGN KEY (no_po) REFERENCES pembelian (no_po),
                FOREIGN KEY (kode_barang) REFERENCES barang (kode_barang)
            )
        ''')

        # 6. Piutang (AR) & Hutang (AP)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS piutang (
                id_piutang TEXT PRIMARY KEY,
                no_invoice TEXT,
                sisa_tagihan REAL NOT NULL,
                tgl_jatuh_tempo TEXT,
                status TEXT DEFAULT 'Pending',
                FOREIGN KEY (no_invoice) REFERENCES penjualan (no_invoice)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS hutang (
                id_hutang TEXT PRIMARY KEY,
                no_po TEXT,
                sisa_hutang REAL NOT NULL,
                tgl_jatuh_tempo TEXT,
                status TEXT DEFAULT 'Pending',
                FOREIGN KEY (no_po) REFERENCES pembelian (no_po)
            )
        ''')

        # 7. Jurnal Keuangan (Buku Besar)
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS jurnal (
                id_jurnal INTEGER PRIMARY KEY AUTOINCREMENT,
                tanggal TEXT NOT NULL,
                kode_akun TEXT,
                ref_transaksi TEXT,
                debit REAL DEFAULT 0,
                kredit REAL DEFAULT 0,
                keterangan TEXT,
                FOREIGN KEY (kode_akun) REFERENCES coa (kode_akun)
            )
        ''')
        
        self.conn.commit()

    def seed_coa(self):
        """Mengisi data awal Chart of Accounts (CoA)"""
        default_accounts = [
            ('1101', 'Kas & Bank', 'Aktiva'),
            ('1102', 'Piutang Usaha Penjualan', 'Aktiva'),
            ('1301', 'Persediaan Barang Dagang', 'Aktiva'),
            ('2101', 'Hutang Usaha Pembelian', 'Kewajiban'),
            ('4001', 'Pendapatan Penjualan ERP', 'Pemasukan'),
            ('5001', 'Beban Harga Pokok Penjualan (HPP)', 'Pengeluaran'),
            ('5002', 'Beban Operasional & Gaji', 'Pengeluaran')
        ]
        self.cursor.executemany(
            'INSERT OR IGNORE INTO coa (kode_akun, nama_akun, kategori) VALUES (?, ?, ?)',
            default_accounts
        )
        self.conn.commit()

    # --- MASTER DATA TRANSAKSI ---
    def tambah_pelanggan(self, id_p, nama, telp, alamat):
        self.cursor.execute(
            'INSERT OR REPLACE INTO pelanggan VALUES (?, ?, ?, ?)',
            (id_p, nama, telp, alamat)
        )
        self.conn.commit()

    def tambah_barang(self, kode, nama, h_beli, h_jual, stok):
        self.cursor.execute(
            'INSERT OR REPLACE INTO barang VALUES (?, ?, ?, ?, ?)',
            (kode, nama, h_beli, h_jual, stok)
        )
        self.conn.commit()

    # --- TRANSAKSI PENJUALAN ---
    def catat_penjualan(self, no_inv, id_pelanggan, items, kredit=False, jatuh_tempo=""):
        """
        items = [ {'kode_barang': 'BRG01', 'jumlah': 2}, ... ]
        """
        tgl_skrg = datetime.now().strftime("%Y-%m-%d")
        total_penjualan = 0

        # Calculate totals and check stock
        for item in items:
            self.cursor.execute('SELECT harga_jual, stok FROM barang WHERE kode_barang = ?', (item['kode_barang'],))
            row = self.cursor.fetchone()
            if not row or row[1] < item['jumlah']:
                raise ValueError(f"Stok barang {item['kode_barang']} tidak mencukupi!")
            subtotal = row[0] * item['jumlah']
            item['subtotal'] = subtotal
            total_penjualan += subtotal

        # Insert Header Penjualan
        self.cursor.execute('INSERT INTO penjualan VALUES (?, ?, ?, ?)', (no_inv, tgl_skrg, id_pelanggan, total_penjualan))

        # Insert Detail & Update Stock
        for item in items:
            self.cursor.execute(
                'INSERT INTO detail_penjualan (no_invoice, kode_barang, jumlah, subtotal) VALUES (?, ?, ?, ?)',
                (no_inv, item['kode_barang'], item['jumlah'], item['subtotal'])
            )
            self.cursor.execute(
                'UPDATE barang SET stok = stok - ? WHERE kode_barang = ?',
                (item['jumlah'], item['kode_barang'])
            )

        # Record Journal Entries (Posting Akuntansi)
        if kredit:
            # Debit Piutang Usaha (1102), Kredit Pendapatan (4001)
            self.cursor.execute('INSERT INTO jurnal (tanggal, kode_akun, ref_transaksi, debit, kredit, keterangan) VALUES (?, ?, ?, ?, ?, ?)',
                                (tgl_skrg, '1102', no_inv, total_penjualan, 0, f"Piutang Penjualan Inv #{no_inv}"))
            # Record Piutang Entity
            self.cursor.execute('INSERT INTO piutang VALUES (?, ?, ?, ?, ?)',
                                (f"AR-{no_inv}", no_inv, total_penjualan, jatuh_tempo, 'Pending'))
        else:
            # Debit Kas (1101), Kredit Pendapatan (4001)
            self.cursor.execute('INSERT INTO jurnal (tanggal, kode_akun, ref_transaksi, debit, kredit, keterangan) VALUES (?, ?, ?, ?, ?, ?)',
                                (tgl_skrg, '1101', no_inv, total_penjualan, 0, f"Kas Penjualan Tunai Inv #{no_inv}"))

        self.cursor.execute('INSERT INTO jurnal (tanggal, kode_akun, ref_transaksi, debit, kredit, keterangan) VALUES (?, ?, ?, ?, ?, ?)',
                            (tgl_skrg, '4001', no_inv, 0, total_penjualan, f"Penjualan Inv #{no_inv}"))

        self.conn.commit()
        print(f"✅ Penjualan Invoice #{no_inv} sebesar Rp {total_penjualan:,.0f} Berhasil Dicatat.")

    # --- LAPORAN RINGKASAN ---
    def tampilkan_laporan_laba_rugi(self):
        self.cursor.execute('''
            SELECT c.nama_akun, SUM(j.debit) as total_debit, SUM(j.kredit) as total_kredit
            FROM jurnal j
            JOIN coa c ON j.kode_akun = c.kode_akun
            WHERE c.kategori IN ('Pemasukan', 'Pengeluaran')
            GROUP BY j.kode_akun
        ''')
        rows = self.cursor.fetchall()
        
        print("\n==========================================")
        print("     LAPORAN LABA RUGI (PROFIT & LOSS)    ")
        print("==========================================")
        total_pemasukan = 0
        total_pengeluaran = 0
        
        for r in rows:
            nama_akun, deb, kre = r
            nominal = kre - deb if kre > deb else deb - kre
            print(f"- {nama_akun:<30}: Rp {nominal:12,.0f}")
            if kre > deb:
                total_pemasukan += nominal
            else:
                total_pengeluaran += nominal
                
        laba_bersih = total_pemasukan - total_pengeluaran
        print("------------------------------------------")
        print(f"TOTAL PEMASUKAN            : Rp {total_pemasukan:12,.0f}")
        print(f"TOTAL PENGELUARAN          : Rp {total_pengeluaran:12,.0f}")
        print(f"LABA (RUGI) BERSIH         : Rp {laba_bersih:12,.0f}")
        print("==========================================\n")

if __name__ == "__main__":
    db = EcountERPDatabase()
    
    # Setup Data Contoh
    db.tambah_pelanggan("CUST-001", "PT Teknologi Nusantara", "08123456789", "Jakarta")
    db.tambah_barang("BRG-01", "Lisensi ECOUNT ERP Standard", 500000, 700000, 50)
    db.tambah_barang("BRG-02", "Modul Tambahan WMS", 300000, 450000, 30)

    # Simulasikan Penjualan Tunai
    db.catat_penjualan("INV-202611-001", "CUST-001", [
        {'kode_barang': 'BRG-01', 'jumlah': 2},
        {'kode_barang': 'BRG-02', 'jumlah': 1}
    ], kredit=False)

    # Simulasikan Penjualan Kredit (Piutang)
    db.catat_penjualan("INV-202611-002", "CUST-001", [
        {'kode_barang': 'BRG-01', 'jumlah': 5}
    ], kredit=True, jatuh_tempo="2026-12-15")

    # Tampilkan Laporan Laba Rugi
    db.tampilkan_laporan_laba_rugi()
