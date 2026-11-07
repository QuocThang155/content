# SRS — Story42 Python Offline Studio

**Phiên bản tài liệu:** 1.0  
**Phiên bản ứng dụng:** 2.0.0  
**Ngày lập:** 07/11/2026  
**Trạng thái:** Đặc tả chức năng cho bản Python desktop đã bàn giao  
**Đơn vị sử dụng:** Người sản xuất truyện Philippine Taglish trên Facebook bằng 3 AI dùng qua giao diện web  

---

## 1. Giới thiệu

### 1.1. Mục tiêu

Story42 là ứng dụng desktop chạy trên máy người dùng nhằm **chuẩn bị ý tưởng, tạo prompt và điều phối 42 truyện/ngày cho 3 AI**, theo mô hình kết hợp tự động và thao tác thủ công. Dự án ưu tiên **không sử dụng API trả phí**, không yêu cầu gửi lại văn bản truyện dài vào ứng dụng và giảm thao tác lặp.

Ứng dụng **không tự điều khiển 3 website AI**, không tự viết 3.000 từ và không tự đăng Facebook. Người vận hành sao chép prompt sang giao diện AI và lấy thành phẩm trực tiếp tại đó. Ứng dụng chỉ lưu thông tin **thẻ cốt truyện**, không giữ nguyên văn truyện đã viết.

### 1.2. Phạm vi bản phát hành

- Chạy bằng **Python 3.10 trở lên** cùng Tkinter; không cài thêm thư viện pip.
- Có 3 khu vực: **Điều phối 3 AI**, **Bổ sung 42 ý tưởng**, **Lịch sử & sao lưu**.
- Có 84 thẻ cốt truyện mẫu thuộc 14 nhóm chủ đề; mỗi nhóm có 6 thẻ.
- Tạo 42 thẻ/ngày bằng cách lấy 3 thẻ chưa dùng từ mỗi nhóm; phân cho 3 AI, mỗi AI 14 thẻ.
- Sao chép prompt viết truyện bằng một nút, tự cập nhật trạng thái “Đã giao”.
- Sửa thẻ cốt truyện, xuất prompt toàn truyện hoặc PART 1 / PART 2.
- Tạo prompt yêu cầu mỗi AI đề xuất 14 ý tưởng mới; nhập 14 dòng kết quả dạng văn bản ngắn.
- Cảnh báo ý tưởng gần nhau bằng phương pháp so từ khóa; **không cam kết loại bỏ mọi trùng lặp về ngữ nghĩa**.
- Tự lưu trạng thái cục bộ; xuất/khôi phục JSON và xuất CSV.

### 1.3. Ngoài phạm vi

- Đăng nhập AI, gọi API, trình duyệt tự click, nhập lệnh tự động vào website AI.
- Tự nhận biết AI đã viết xong, tự lấy toàn văn hoặc tự xuất bản Facebook.
- Chứng minh bản quyền/đạo văn, đánh giá ngữ nghĩa tuyệt đối hoặc bảo đảm 42 tác phẩm không cùng mô-típ.
- Tự kiểm tra nội dung hoàn chỉnh khi người dùng không cung cấp nội dung đó.
- Đảm bảo hạn mức sử dụng của các dịch vụ AI miễn phí.

### 1.4. Thuật ngữ

| Thuật ngữ | Giải thích |
|---|---|
| Thẻ cốt truyện (brief) | Dữ liệu ngắn về nhân vật, bất công, bằng chứng, đảo chiều và kết thúc; không phải truyện hoàn chỉnh |
| Seed | Một thẻ cốt truyện mẫu có sẵn trong mã nguồn |
| Kho ý tưởng (library) | Danh sách brief gốc và brief được nhập thêm, có ID riêng |
| AI 1–3 | Ba giao diện AI người dùng tự vận hành; ứng dụng không có kết nối trực tiếp |
| Prompt | Đoạn chỉ dẫn được sao chép để dán vào AI |
| Nhật ký ngày | Danh sách brief, phân công và trạng thái của một ngày |

---

## 2. Người dùng và điều kiện vận hành

### 2.1. Người dùng chính

Một biên tập viên/sản xuất nội dung quản lý tối đa 3 AI chạy đồng thời trên các tab/trình duyệt riêng. Người dùng có thể chỉnh sửa Python trong VS Code nhưng **không bắt buộc biết lập trình** để dùng ứng dụng.

### 2.2. Điều kiện hệ thống

| Mục | Yêu cầu |
|---|---|
| Hệ điều hành | Windows 10/11, macOS hoặc Linux có giao diện đồ họa |
| Python | 3.10+ (khuyến nghị 3.11+) |
| Tkinter | Phải có trong bản cài Python; trên một số Linux cài thêm `python3-tk` từ trình quản lý gói hệ điều hành |
| Internet | Không cần để mở và quản lý Story42; cần nếu người dùng gửi prompt qua dịch vụ AI trên web |
| API / token | Không cần; không lưu mật khẩu hay thông tin đăng nhập AI |
| Dữ liệu cục bộ | `~/.story42_offline/project.json` (thư mục người dùng trên hệ điều hành) |
| Môi trường lập trình | Có thể chạy từ terminal VS Code |

---

## 3. Quy trình nghiệp vụ mục tiêu

```text
[Kho 84 ý tưởng + ý tưởng mới]
             |
             v
[Phân 42 brief, 14 brief / AI]
             |
             v
[Rà soát khả năng trùng ý tưởng trước khi viết]
             |
        +----+----+
        |    |    |
       AI1  AI2  AI3
        |    |    |
[Sao chép prompt từ ứng dụng, dán thủ công sang AI]
        |    |    |
[AI tự viết và tự kiểm tra theo nội dung prompt]
        |    |    |
[Biên tập viên kiểm tra ngay trên AI và lấy truyện để đăng]
             |
             v
 [Bấm hoàn tất trong Story42]
             |
             v
       [Lưu tiến độ JSON]
```

**Nguyên tắc cứng:** không có bước sao chép truyện hoàn chỉnh từ AI trở lại Story42.

### 3.1. Luồng vận hành hằng ngày

1. Mở chương trình, chọn ngày. Nếu chưa có dữ liệu và kho ý tưởng chưa hết, chương trình tạo 42 brief.
2. Rà soát 42 brief; sửa brief có nội dung quá gần nhau hoặc chưa hợp lý.
3. Mỗi AI bấm **Sao chép tiếp** để nhận prompt tiếp theo của mình.
4. Dán prompt vào AI tương ứng. Sau khi hoàn tất, lấy bản truyện trực tiếp từ AI để sử dụng.
5. Bấm **✓ Xong** tại thẻ để ghi trạng thái hoàn tất.
6. Cuối ngày, có thể xuất CSV để xem tiến độ và JSON để sao lưu.

### 3.2. Luồng khi hết ý tưởng mẫu

1. Chọn ngày cần tạo, mở **Bổ sung 42 ý tưởng**.
2. Chọn **AI 1**, bấm **Sao chép lệnh tạo 14 ý tưởng**; gửi lệnh cho AI 1.
3. Sao chép **14 dòng brief ngắn** từ AI 1 (không phải 14 truyện hoàn chỉnh), dán vào ô nhập; bấm **Nhập 14 ý tưởng cho AI đã chọn**.
4. Lặp lại với AI 2 rồi AI 3. Kết quả: 42 brief mới của ngày.
5. Bấm **Rà trùng ý tưởng**, xem lại các cảnh báo trước khi viết.

**Giới hạn đã biết:** Kho mẫu có 84 brief, tương đương tối đa 2 ngày với 42 brief/ngày nếu không bổ sung thêm. Việc tạo ra ý tưởng mới dài hạn vẫn cần AI qua giao diện web hoặc sự sáng tạo của người dùng. Không được tái sử dụng seed đã giao ở những ngày trước như một ý tưởng “mới”.

---

## 4. Yêu cầu chức năng

### FR-01 — Khởi tạo dữ liệu

- Khi chạy lần đầu, tạo dữ liệu mặc định với kho 84 brief mẫu.
- Mỗi brief có ID duy nhất, nhóm chủ đề, tiêu đề, vai chính, phản diện, hành động bất công, bằng chứng, đảo chiều, kết thúc.
- Mỗi ngày lưu độc lập, có thể chuyển ngày làm việc qua trường YYYY-MM-DD.
- Không được ghi đè ngày đã có dữ liệu chỉ vì mở lại chương trình.

**Tiêu chí nghiệm thu:** chạy ngày đầu có 42 brief, ngày thứ hai có 42 brief khác ID; không phát sinh thẻ đã sử dụng ở ngày trước.

### FR-02 — Phân công 3 AI

- 42 brief được chia thành 3 luồng AI 1, AI 2, AI 3; mỗi luồng 14 brief.
- Với mỗi nhóm chủ đề, phải có đúng 3 brief/ngày, mỗi AI nhận một brief.
- Mỗi brief có số `slot` duy nhất trong ngày.

**Tiêu chí nghiệm thu:** không có AI nhận 13 hoặc 15 brief khi đủ 42 đầu vào.

### FR-03 — Giao diện điều phối

- Hiển thị 3 cột AI với danh sách thẻ, trạng thái, nút sao chép, nút sửa, nút hoàn tất.
- Hiển thị tổng số thẻ, số hoàn tất, số đang xử lý, số chưa giao.
- Nút **Sao chép tiếp** tìm thẻ `ready` đầu tiên của AI đang chọn và sao chép prompt toàn truyện.

**Tiêu chí nghiệm thu:** người vận hành không phải tìm và chọn thủ công prompt kế tiếp nếu chỉ muốn giao truyện mới.

### FR-04 — Tạo prompt viết truyện

- Tự chèn thông tin của thẻ vào prompt English yêu cầu đầu ra Philippine Taglish.
- Có chế độ 1 lượt: HOOK khoảng 25 từ, PART 1 khoảng 700 từ, PART 2 khoảng 2.300 từ; tổng khoảng 3.000 từ.
- Có phương án sao chép PART 1 hoặc PART 2 khi AI bị giới hạn độ dài.
- Prompt chứa yêu cầu chống lặp, đối thoại tự nhiên, có bằng chứng và cú đảo chiều hợp lý, an toàn Facebook/YouTube.
- Prompt yêu cầu AI tự rà soát trước khi xuất; không yêu cầu người dùng gửi lại bản hoàn chỉnh cho phần mềm.

**Tiêu chí nghiệm thu:** bấm “Sao chép” rồi dán vào một ô văn bản phải có nguyên prompt tương ứng thẻ.

### FR-05 — Trạng thái

- `ready`: chưa giao.
- `sent`: đã sao chép prompt toàn truyện hoặc PART 2.
- `part1`: đã sao chép prompt PART 1.
- `done`: đã hoàn tất theo xác nhận thủ công của người dùng.
- Sao chép prompt làm thay đổi trạng thái tương ứng, ngoại trừ thẻ đã `done`.
- Bấm **✓ Xong** chuyển sang `done`; bấm hoàn tác chuyển về `sent`.
- Cập nhật nào cũng được ghi xuống file dữ liệu ngay.

**Tiêu chí nghiệm thu:** đóng/mở chương trình không mất trạng thái đã lưu.

### FR-06 — Chỉnh sửa brief

- Cho phép sửa 7 trường nội dung, giữ nguyên nhóm chủ đề, ID, AI và slot.
- Có các nút **Lưu & đóng**, **Sao chép cả bài**, **Sao chép P1**, **Sao chép P2**, **Kiểm tra gần giống**.
- Kiểm tra độ dài tối thiểu các trường trước khi lưu.

**Tiêu chí nghiệm thu:** sửa một bằng chứng phải làm prompt sao chép lần sau chứa bằng chứng mới.

### FR-07 — Rà soát trùng ý tưởng (mức sơ bộ)

- So sánh từ khóa giữa phần bất công, bằng chứng, đảo chiều và tiêu đề; tính điểm tương đồng từ 0 đến 1.
- Nút rà soát toàn ngày liệt kê các cặp có điểm từ ngưỡng được cấu hình.
- Nút rà soát một brief đối chiếu với brief cùng ngày và các ngày đã lưu.
- Khi nhập batch 14 brief mới, nếu điểm tương đồng đáng kể, cảnh báo và để người dùng quyết định.
- Hệ thống phải thông báo rằng đây **không phải bộ kiểm tra ngữ nghĩa hoặc bản quyền hoàn chỉnh**.

**Tiêu chí nghiệm thu:** hai brief gần trùng cả hành động bất công, bằng chứng và đảo chiều phải có điểm tương đồng cao hơn hai brief khác chủ đề.

### FR-08 — Tạo lệnh lập kế hoạch 14 ý tưởng

- Với mỗi AI, tạo prompt yêu cầu 14 brief có đủ 7 trường nội dung theo 14 chủ đề được định nghĩa.
- Đưa một phần lịch sử vào danh sách cần tránh lặp.
- Định dạng trả về yêu cầu 14 dòng, mỗi dòng 8 cột phân tách bằng ` || `, bắt đầu từ `01` tới `14`.
- Gửi lệnh cho AI qua **clipboard**, không qua API.

**Tiêu chí nghiệm thu:** có thể sao chép và gửi lệnh trên một dịch vụ AI bất kỳ bằng cách dán thủ công.

### FR-09 — Nhập 14 ý tưởng mới

- Chấp nhận 14 dòng đúng format, mỗi dòng gồm số thứ tự + 7 mô tả.
- Lưu thành brief mới với ID `CUSTOM-...`.
- Chỉ thay lane AI đang chọn và **không thay lane đã có prompt được gửi**.
- Giữ nguyên các lane AI khác trong ngày.
- Thêm brief mới vào thư viện; ID đã xuất hiện trong một ngày không được tự động chọn lại cho ngày tương lai.

**Tiêu chí nghiệm thu:** nhập 14 dòng cho AI 1 và 14 dòng cho AI 2 không làm mất dữ liệu của nhau.

### FR-10 — Lịch sử và sao lưu

- Tự lưu `project.json` sau các thay đổi; ghi file tạm trước khi thay file dữ liệu để giảm nguy cơ hỏng file khi ghi.
- Tab lịch sử cho biết từng ngày có bao nhiêu thẻ, số đã giao và số hoàn tất.
- Cho phép xuất JSON, khôi phục JSON sau xác nhận ghi đè và xuất CSV theo ngày.
- UTF-8 cho JSON; UTF-8 có BOM cho CSV để Excel Windows đọc tiếng Việt tốt hơn.

**Tiêu chí nghiệm thu:** xuất JSON và khôi phục phải lấy lại ngày, thư viện và các trạng thái.

### FR-11 — Không lưu toàn văn truyện

- Không xây dựng ô nhập 3.000 từ nhằm kiểm tra bài đã viết.
- Không thu thập dữ liệu đăng nhập, số điện thoại, địa chỉ hoặc các bản ghi AI bên ngoài.
- Người vận hành kiểm duyệt thành phẩm trực tiếp trên giao diện AI và có thể lưu/đăng theo công cụ riêng.

**Tiêu chí nghiệm thu:** thao tác hoàn tất chỉ cần nhấn nút; không yêu cầu dán nội dung truyện.

---

## 5. Quy tắc cốt truyện và chống trùng

### 5.1. Những chiều cần khác nhau

Một brief được đánh giá có bản sắc khi có khác biệt đáng kể ở **bối cảnh**, **vai chính**, **hành động bất công**, **loại bằng chứng**, **cơ chế đảo chiều**, **cách kết thúc**. Hai brief chỉ thay tên riêng hoặc địa điểm nhưng giữ nguyên diễn biến cần được xem là chưa đủ khác biệt.

### 5.2. Phạm vi bảo đảm thực tế

- Hệ thống có thể bảo đảm **không tự chọn lại đúng cùng ID brief** đã tồn tại trong lịch sử.
- Hệ thống kiểm tra bằng phương pháp từ khóa; những trường hợp dùng từ khác nhưng ý nghĩa giống nhau **có thể bị bỏ sót**.
- Tất cả 42 bài vẫn có cùng phong cách/genre tổng thể **Philippine Taglish drama** theo yêu cầu, nên không thể bảo đảm 42 bài thuộc 42 thể loại hoàn toàn khác nhau.
- Người dùng có trách nhiệm duyệt những đề cương na ná nhau trước khi gửi AI.
- Truyện hoàn chỉnh còn có khả năng giống nhau về kết cấu hoặc thoại dù brief khác nhau; do không nhận nội dung truyện, Story42 không thể phát hiện hoặc bảo đảm điều này.

### 5.3. Chiến lược vận hành được khuyến nghị

- Mỗi ngày 14 nhóm × 3 ý tưởng, không lặp chứng cứ và đảo chiều trong cùng nhóm.
- Khi bổ sung brief bằng AI, yêu cầu ý tưởng mới có động cơ nhân vật rõ và bằng chứng hợp lý, không sử dụng bài gốc có bản quyền làm bản viết lại tối thiểu.
- Người duyệt tập trung đọc **xung đột → bằng chứng → cú đảo chiều** của 42 thẻ trước khi bấm sao chép.

---

## 6. Yêu cầu phi chức năng

| ID | Yêu cầu | Mức độ |
|---|---|---|
| NFR-01 | Ứng dụng hoạt động offline, không phát sinh API call | Bắt buộc |
| NFR-02 | Không phụ thuộc gói pip ngoài Python chuẩn | Bắt buộc |
| NFR-03 | Giao diện bằng tiếng Việt; nội dung prompt đầu ra tiếng Anh để yêu cầu AI viết Taglish | Bắt buộc |
| NFR-04 | Tự lưu sau khi thay trạng thái và chỉnh brief | Bắt buộc |
| NFR-05 | Có thông báo nếu hết brief mới; không âm thầm dùng lại brief | Bắt buộc |
| NFR-06 | Không tự đăng Facebook, không dùng công cụ điều khiển website AI | Bắt buộc |
| NFR-07 | Không lưu toàn văn bài đã viết, dữ liệu đăng nhập hoặc khóa API | Bắt buộc |
| NFR-08 | Sử dụng được với chuột/bàn phím, cửa sổ tối thiểu khoảng 1040×660 | Mong muốn |
| NFR-09 | Mọi phép kiểm tra trùng chỉ được mô tả là heuristic, không phải chứng minh tuyệt đối | Bắt buộc |
| NFR-10 | Đọc/ghi JSON UTF-8; xuất CSV mở được trong Excel | Bắt buộc |

---

## 7. Thiết kế dữ liệu

### 7.1. Cấu trúc JSON

```json
{
  "version": 2,
  "library": [
    {
      "id": "SEED-001",
      "source": "starter",
      "theme": "FAMILY",
      "title": "The Empty Chair",
      "hero": "...",
      "antagonist": "...",
      "conflict": "...",
      "evidence": "...",
      "reversal": "...",
      "ending": "..."
    }
  ],
  "days": {
    "2026-11-07": {
      "created": "2026-11-07T16:00:00",
      "items": [
        {
          "id": "SEED-001",
          "uid": "random-entry-identifier",
          "slot": 1,
          "ai": 1,
          "status": "ready",
          "theme": "FAMILY",
          "title": "The Empty Chair",
          "hero": "...",
          "antagonist": "...",
          "conflict": "...",
          "evidence": "...",
          "reversal": "...",
          "ending": "..."
        }
      ]
    }
  },
  "history": []
}
```

Lưu ý: ví dụ trên lược bớt dữ liệu. Dữ liệu `history` hiện là trường dự phòng; màn hình lịch sử được tổng hợp trực tiếp từ `days`.

### 7.2. Nguyên tắc quản lý ID

`id` là danh tính nội dung brief trong thư viện; `uid` là danh tính một lần xuất hiện trong ngày; `slot` là vị trí 1–42; `ai` thuộc 1, 2, 3. Trạng thái áp dụng cho một lần xuất hiện của brief trong ngày.

---

## 8. Giao diện người dùng

### 8.1. Tab 1: 3 AI — Điều phối

- Thanh trên: logo, ngày làm việc, đổi/tạo ngày.
- Bốn ô thống kê: tổng thẻ, hoàn tất, đang xử lý, chưa giao.
- Ba cột AI 1, AI 2, AI 3, mỗi cột có nút **Sao chép tiếp**.
- Mỗi thẻ: số, nhóm, tiêu đề, tóm tắt bất công, trạng thái, các nút.
- Nút chung: **Rà trùng ý tưởng**, **Xuất CSV**.

### 8.2. Tab 2: Bổ sung 42 ý tưởng

- Chọn AI 1/2/3.
- Nút **Sao chép lệnh tạo 14 ý tưởng**.
- Ô nhập 14 dòng brief, không nhập truyện dài.
- Nút **Nhập 14 ý tưởng cho AI đã chọn**.

### 8.3. Tab 3: Lịch sử & sao lưu

- Thống kê các ngày đã có dữ liệu, số thẻ đã giao, số hoàn tất.
- Nút xuất JSON, nhập JSON và xuất CSV.
- Hiển thị đường dẫn file lưu tự động.

---

## 9. Các tình huống ngoại lệ

| Tình huống | Xử lý |
|---|---|
| Dùng hết 84 seed mà không bổ sung ý tưởng | Báo thiếu brief, không lặp seed cũ; người dùng nhập ý tưởng mới |
| Dán không đủ 14 dòng brief | Từ chối nhập, nêu lỗi và giữ nguyên dữ liệu |
| Dòng brief thiếu trường | Từ chối và hiển thị số dòng có lỗi |
| Nhập brief trùng từ khóa rõ rệt | Cảnh báo, cho phép người dùng xem xét và xác nhận |
| Cố ghi đè 14 thẻ đã giao | Chặn để tránh mất trạng thái công việc |
| File JSON khôi phục không đúng schema | Báo lỗi, không thay dữ liệu hiện tại |
| Không có Tkinter hoặc không có desktop | Hướng dẫn cài Tkinter/chạy trong hệ điều hành đồ họa |
| Clipboard của OS không khả dụng | Báo lỗi thay vì tự đánh dấu truyện đã giao |
| Lưu file gặp lỗi phân quyền | Báo lỗi và gợi ý dùng xuất bản sao JSON |

---

## 10. Kiểm thử và tiêu chí nghiệm thu

### 10.1. Kiểm thử tự động trong source

Chạy:

```bash
python Story42.py --self-test
```

Bộ test tích hợp gồm:

1. Kho có 84 brief, mỗi nhóm 6 brief, tiêu đề không trùng.
2. Hai ngày đầu tạo được đúng 42 brief/ngày, 14 brief/AI và 3 brief/nhóm; sau đó không tự tái sử dụng 84 seed.
3. Prompt cả truyện, PART 1, PART 2 có yêu cầu Taglish.
4. Bộ phân tích nhập chấp nhận 14 dòng đúng format và từ chối 13 dòng.
5. Lưu/đọc file JSON và so sánh từ khóa chạy được.

### 10.2. Kiểm thử thủ công UI cần thực hiện

- Mở chương trình trên Windows/macOS/Linux thực tế bằng VS Code.
- Bấm **Sao chép tiếp** AI 1, dán thử vào ứng dụng văn bản và xác nhận prompt đúng thẻ.
- Bấm **✓ Xong**, đóng mở ứng dụng và xác nhận trạng thái không mất.
- Chỉnh một brief rồi kiểm tra prompt sao chép đã đổi.
- Sao chép PART 1 rồi PART 2 vào cùng cuộc trò chuyện AI và đọc lại kết quả.
- Xuất JSON/CSV, khôi phục dữ liệu; kiểm tra Unicode tiếng Việt.
- Gửi lệnh tạo 14 brief cho một AI ngoài ứng dụng; thử nhập phản hồi theo định dạng yêu cầu.

### 10.3. Chỉ số theo dõi thực tế

Người dùng nên tự đo: số lượt sao chép/giao truyện, số lượt AI xuất thiếu từ, số brief bị chỉnh vì gần giống, số truyện thực sự hoàn tất, thời gian kiểm duyệt và tỉ lệ cần viết lại. **Ứng dụng không bảo đảm** đầu ra 42 × 3.000 từ/ngày nếu hạn mức AI không đủ.

---

## 11. Hướng dẫn chạy trong VS Code

1. Tạo thư mục dự án, lưu 2 file `Story42.py` và `SRS_Story42.md` vào cùng một thư mục.
2. Mở thư mục trong Visual Studio Code.
3. Đảm bảo Python 3.10+ đã được cài. Chọn Python Interpreter phù hợp trong VS Code.
4. Mở terminal và chạy:

```bash
python Story42.py
```

Nếu Windows dùng Python launcher:

```powershell
py Story42.py
```

Nếu một bản Linux không có Tkinter, cài bằng trình quản lý gói hệ điều hành (ví dụ Ubuntu/Debian):

```bash
sudo apt install python3-tk
```

Để chạy test mà không cần mở giao diện:

```bash
python Story42.py --self-test
```

Dữ liệu phát sinh sẽ tự lưu tại `~/.story42_offline/project.json`, **không ghi đè file source code**. Sao lưu định kỳ qua tab Lịch sử & sao lưu.

---

## 12. Kế hoạch mở rộng trong tương lai (chưa triển khai)

| Ưu tiên | Hạng mục | Lý do |
|---|---|---|
| P1 | Bộ so trùng theo nhãn conflict/evidence/twist do người dùng duyệt | Chính xác hơn từ khóa nhưng vẫn không cần API |
| P1 | Hàng đợi điều phối theo deadline, độ dài và độ ưu tiên | Giảm chọn thủ công vào ngày đông bài |
| P2 | Import/export brief từ Excel/CSV được chuẩn hóa | Dễ duyệt kho lớn |
| P2 | Khả năng lưu nhiều bộ quy tắc phong cách Taglish | Dùng nhiều fanpage có tông riêng |
| P2 | Gợi ý tạo mới từ cấu trúc nội bộ có giám sát | Mở rộng hơn 84 seed, tránh cấu trúc vô lý |
| P3 | Bản cài `.exe` cho Windows | Không phải mở VS Code để dùng |

---

## 13. Cam kết và giới hạn

**Đã có trong bản giao:** ứng dụng Tkinter offline, kho 84 brief, phân 42/3 AI, tạo và sao chép prompt, thay đổi trạng thái, nhập 14 brief, cảnh báo sơ bộ, JSON và CSV.

**Chưa có và không được quảng cáo là đã có:** tự kết nối AI, tự viết bài, tự đăng, phân tích toàn văn không cung cấp đầu vào, chống trùng ngữ nghĩa/bản quyền tuyệt đối, bảo đảm chất lượng đầu ra hoặc số lượng 42 bài được tạo mỗi ngày.

**Định hướng thiết kế được giữ vững:** mọi bước kiểm soát ý tưởng nằm **trước khi viết**; truyện sau khi viết được kiểm tra thủ công trên chính dịch vụ AI, **không phải sao chép ngược trở lại Story42**.
