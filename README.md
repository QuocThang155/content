# Đặc tả yêu cầu phần mềm — THẮNG MIA

**Phiên bản:** 3.2.0
**Ngày cập nhật:** 08/11/2026
**Trạng thái:** Đặc tả theo mã nguồn hiện tại

## 1. Mục đích và phạm vi

THẮNG MIA là ứng dụng web chạy cục bộ, hỗ trợ người dùng quản lý 42 brief cốt
truyện mỗi ngày cho ba phiên AI được người dùng vận hành thủ công.
Ứng dụng chỉ quản lý brief, prompt và tiến độ giao việc; không tự gọi dịch vụ
AI, không tự động điều khiển website AI, không lưu truyện hoàn chỉnh và không
đăng nội dung lên mạng xã hội.

Giao diện người dùng bằng tiếng Việt. Nội dung prompt viết truyện do người dùng
tự cấu hình; hệ thống chỉ thay các biến brief được cho phép.

### 1.1. Định danh dự án
| Thành phần | Tên chuẩn |
|---|---|
| Tên dự án | `thangmia` |
| GitHub repository | `thangmia` |
| Tên trên giao diện | **THẮNG MIA** |
| Frontend package | `thangmia-frontend` |
| Backend API | `thangmia API` |
| Thư mục output | `thangmia_output` |

## 2. Kiến trúc và công nghệ

| Thành phần | Công nghệ và trách nhiệm |
|---|---|
| Giao diện | React 19, Next.js 16 App Router, TypeScript, CSS responsive và Lucide icons |
| API | Python, FastAPI, Pydantic và Uvicorn |
| Luật nghiệp vụ | `backend/core.py`, không phụ thuộc Tkinter hay giao diện |
| Lưu trữ | SQLite cục bộ; một tài liệu JSON schema v2 được lưu trong một bản ghi |
| Kết nối trình duyệt | Frontend gọi `/api/*`; Next.js rewrite request tới FastAPI |
| Sao chép | Clipboard API của trình duyệt, có fallback `document.execCommand('copy')` |

Mặc định `thangmia API` sử dụng:

```text
~/.thangmia/thangmia.sqlite3
```

Có thể đổi vị trí bằng biến môi trường `THANGMIA_DB_PATH`. Nếu database cũ ở
`~/.story42_web/story42.sqlite3` tồn tại mà database mới chưa có, backend sẽ
sao lưu rồi tự động sao chép dữ liệu sang đường dẫn mới; database cũ không bị
xóa hoặc ghi đè. Dữ liệu được đọc và
ghi trong giao dịch SQLite `BEGIN IMMEDIATE` để tránh mất cập nhật khi có
nhiều request đồng thời.

Prompt Full do template người dùng cấu hình có thể được xuất thành 14 file TXT
cho từng lane qua nút **Xuất 14 TXT** trong Workflow. Workspace dùng biến môi trường
`THANGMIA_WORKSPACE_DIR`, mặc định `~/.thangmia/workspace/`, với ba thư mục
`AI1`, `AI2` và `AI3`. File dùng tên `YYYY-MM-DD_AIn_NN.txt`; file input hoặc
`_output.txt` đã tồn tại sẽ được bỏ qua và không thay đổi trạng thái nghiệp vụ.
Khi chạy Docker, workspace trên host phải được mount vào backend và trỏ cùng
thư mục mà Chrome Extension chọn.

Trên Windows, có thể cấu hình workspace cố định bằng đường dẫn tuyệt đối, ví
dụ `D:\thang\workspace`. Cấu hình hiện tại của môi trường Windows dùng đường
dẫn này; dữ liệu workspace cũ không bị xóa khi chuyển vị trí. Backend tạo và
kiểm tra quyền đọc/ghi các thư mục `AI1`, `AI2` và `AI3` trước khi sử dụng.

Mỗi lần xuất prompt, backend lưu manifest
`.thangmia_manifest.json` trong workspace. Manifest ánh xạ ngày, lane, slot,
`uid`, tên file prompt, tên file output, hash prompt, phiên bản prompt và hash
output. File không có mapping hợp lệ hoặc có `uid` không khớp không được tự
động gán cho brief.

## 3. Mô hình dữ liệu và quy tắc phân bổ

### 3.1. Brief

Mỗi brief có các trường nội dung:

- `title`: tiêu đề;
- `hero`: nhân vật chính;
- `antagonist`: nhân vật gây xung đột;
- `conflict`: hành động hoặc tình huống bất công;
- `evidence`: bằng chứng;
- `reversal`: cú đảo chiều;
- `ending`: kết thúc.

Mỗi brief còn có các trường hệ thống:

- `id`: ID brief, không chỉnh sửa trên giao diện;
- `uid`: định danh của thẻ trong ngày;
- `slot`: vị trí từ 1 đến 42;
- `ai`: AI 1, 2 hoặc 3;
- `theme`: nhóm chủ đề;
- `source`: nguồn brief;
- `status`: trạng thái xử lý;
- `last_copied`: thời điểm sao chép gần nhất, nếu có.

Các trường nội dung khi chỉnh sửa phải dài từ 7 đến 2.000 ký tự.

### 3.2. Phân bổ trong ngày

- Một ngày có tối đa 42 thẻ: 14 thẻ cho mỗi AI.
- Có 14 nhóm chủ đề; mỗi ngày mặc định phân bổ 3 thẻ cho mỗi nhóm.
- Thư viện ban đầu có 84 starter brief khác nhau, đủ cho hai ngày nếu không
  nhập thêm ý tưởng.
- Khi starter brief đã hết, người dùng phải nhập thêm brief qua tab **Bổ sung
  ý tưởng**.
- Khi thay thế một lane, chỉ được thay thế các thẻ còn ở trạng thái `ready`.
  Lane đã có thẻ `sent`, `part1` hoặc `done` sẽ bị khóa để bảo vệ tiến độ.

### 3.3. Trạng thái

| Trạng thái | Ý nghĩa |
|---|---|
| `ready` | Chưa giao cho AI |
| `sent` | Đã sao chép prompt toàn truyện hoặc Part 2 |
| `part1` | Đã sao chép prompt Part 1 |
| `done` | Người dùng đánh dấu đã hoàn tất xử lý |

Chỉ số **Đang xử lý** bằng số thẻ `sent` cộng số thẻ `part1`. Chỉ số **Đã
ghi nhận** của từng lane bao gồm `sent`, `part1` và `done`; chỉ số **Hoàn tất**
chỉ bao gồm `done`.

## 4. Chức năng người dùng

### 4.1. Menu và Trang chủ

Thanh điều hướng bên trái mang nhãn **MENU** và gồm các mục:

- **Trang chủ:** hiển thị tổng quan số lượng thẻ, tiến độ hoàn tất, số thẻ đang
  xử lý và số thẻ chưa giao theo ngày đã chọn.
- **Workflow:** mở hàng đợi sản xuất và các lane AI.
- **Bổ sung ý tưởng:** nhập thêm brief cho từng AI.
- **Lịch sử & sao lưu:** xem lịch sử ngày, tải bản sao lưu và khôi phục dữ liệu.

Tên thương hiệu hiển thị trên giao diện là **THẮNG MIA**. Trang chủ và
Workflow là hai màn hình riêng; trang chủ không chứa danh sách hàng đợi chi
tiết.

### 4.2. Workflow — Hàng đợi sản xuất

Người dùng có thể:

1. Chọn ngày làm việc.
2. Xem hàng đợi theo ba lane **AI 1**, **AI 2** và **AI 3**.
3. Tìm kiếm theo tiêu đề, chủ đề, nhân vật hoặc slot.
4. Lọc theo `Tất cả`, `Chưa giao`, `Đang xử lý` hoặc `Hoàn tất`.
5. Nhấn **Sao chép tiếp** để chọn thẻ `ready` đầu tiên của lane đó.
6. Mặc định mỗi lane chỉ hiển thị một bài.
7. Nhấn **Bài tiếp theo** để chuyển sang thẻ kế tiếp trong lane đang xem.
8. Nhấn **Xem toàn bộ** để mở toàn bộ thẻ của lane; danh sách này có thanh
   cuộn nội bộ và không làm trang chính cuộn theo.
9. Chọn một bài trong danh sách toàn bộ để thu gọn lane và quay về đúng bài
   đã chọn.
10. Sao chép prompt đầy đủ của bất kỳ thẻ nào.
11. Mở trình chỉnh sửa brief và lưu thay đổi.
12. Sao chép prompt `Full`, `Part 1` hoặc `Part 2` sau khi chỉnh sửa.
13. Đánh dấu thẻ hoàn tất hoặc hoàn tác trạng thái hoàn tất.
14. Xem và lọc số ý tưởng còn lại trong kho.

Thao tác sao chép được thực hiện theo thứ tự:

1. Sinh hoặc lấy prompt.
2. Ghi prompt vào clipboard.
3. Chỉ khi clipboard thành công mới gọi API ghi nhận sao chép.
4. Cập nhật trạng thái và các bộ đếm trên giao diện mà không reload trang.

Nếu trình duyệt từ chối clipboard, trạng thái thẻ không thay đổi.

### 4.3. Hoàn tác sao chép

Với thẻ đang ở trạng thái `sent` hoặc `part1`, người dùng có thể nhấn
**Hoàn tác sao chép**. Hệ thống sẽ:

- chuyển thẻ về `ready`;
- xóa `last_copied`;
- giảm bộ đếm **Đang xử lý**;
- đưa thẻ trở lại hàng đợi **Chưa giao**;
- cập nhật giao diện ngay, không reload trang.

Thẻ `done` không thể hoàn tác sao chép trực tiếp. Người dùng phải hoàn tác
**Hoàn tất** trước, sau đó mới hoàn tác sao chép.

### 4.4. Bổ sung ý tưởng

- Người dùng chọn AI 1, 2 hoặc 3.
- Giao diện cung cấp prompt yêu cầu đúng 14 dòng brief.
- Bộ phân tích yêu cầu mỗi dòng đủ trường theo định dạng parser.
- Nhập thiếu hoặc sai định dạng sẽ bị từ chối.
- Nếu phát hiện ý tưởng gần giống theo từ khóa, giao diện hiển thị cảnh báo và
  yêu cầu xác nhận trước khi tiếp tục.
- Lane chỉ được ghi đè khi người dùng xác nhận và toàn bộ thẻ cũ vẫn là `ready`.
- Brief nhập thủ công có ID dạng `CUSTOM-*` và không tái sử dụng starter ID.

### 4.5. Kiểm tra trùng ý tưởng

Ứng dụng hỗ trợ:

- rà soát các cặp brief trong ngày;
- so sánh một brief với các brief khác và dữ liệu những ngày đã lưu;
- dùng độ tương đồng weighted Jaccard trên từ khóa.

Kết quả chỉ là cảnh báo heuristic, không phải kiểm tra ngữ nghĩa, đạo văn hay
bản quyền.

### 4.6. Lịch sử và sao lưu

Tab **Lịch sử & sao lưu** hỗ trợ:

- xem số thẻ, số thẻ đã giao và số thẻ hoàn tất theo từng ngày;
- tải bản sao lưu JSON schema v2;
- khôi phục toàn bộ dữ liệu từ JSON;
- xác nhận trước khi khôi phục vì thao tác khôi phục ghi đè toàn bộ cơ sở dữ liệu.

JSON v2 tương thích hai chiều với dữ liệu desktop thangmia cũ. File desktop gốc
không bị ghi đè khi nhập vào web.

### 4.7. Quản lý prompt TXT và kết quả Gemini

Trong Workflow, mỗi brief có thể mở hai nội dung riêng:

- **Prompt:** nội dung đầy đủ của file prompt `.txt`;
- **Truyện trả về:** nội dung nguyên văn của file `_output.txt` do Extension
  tạo.

Nếu output chưa tồn tại, giao diện hiển thị **Chưa có kết quả**. Người dùng
có thể làm mới trạng thái file, xem, chỉnh sửa, tải xuống hoặc xóa file với
xác nhận. Việc sửa/xóa file chỉ tác động đến workspace, không xóa hoặc sửa
brief trong SQLite.

Backend kiểm tra xung đột bằng hash trước khi lưu. File được ghi qua file tạm
và đổi tên atomic. Chỉ file `.txt` thuộc workspace và có mapping hợp lệ mới
được đọc, ghi hoặc xóa. Việc phát hiện output không tự chuyển trạng thái
`ready`, `sent`, `part1` hoặc `done`.

### 4.8. Cài đặt Prompt Template

Menu **Cài đặt Prompt** lưu độc lập ba template `Full`, `Part 1` và `Part 2`
trong tài liệu JSON của SQLite. Template mới mặc định là chuỗi rỗng; dữ liệu
database cũ không được dùng để tự tạo hoặc import prompt. Chỉ bảy biến
`{{title}}`, `{{hero}}`, `{{antagonist}}`, `{{conflict}}`, `{{evidence}}`,
`{{reversal}}` và `{{ending}}` được chấp nhận, có thể lặp lại nhiều lần. Biến
khác bị từ chối, không có `eval()` hay thực thi nội dung template.

Người dùng có thể nhập, lưu, xem trước sau khi thay biến, hủy thay đổi và xóa
từng template. Khi template tương ứng chưa cấu hình, API prompt và xuất TXT
trả lỗi rõ ràng; trạng thái brief không thay đổi. Backup/restore JSON giữ
trường `prompt_templates`; backup cũ không có trường này được coi là ba mẫu
trống.

### 4.9. Kho ý tưởng

Menu **Kho ý tưởng** hiển thị tối đa 42 brief của ngày đang chọn, chia thành
ba lane AI với tối đa 14 brief mỗi lane. Người dùng có thể tìm kiếm trong bảy
trường brief, lọc theo trạng thái, sắp xếp theo vị trí/tiêu đề/trạng thái,
xem đầy đủ nội dung và mở trình chỉnh sửa brief hiện có. Ghi chú riêng, cờ
yêu thích và bản nháp được lưu cùng item trong SQLite; không tạo bản sao brief.
Các item liên kết với Workflow bằng `uid`.

Khi workspace đã có prompt hoặc output cho brief, giao diện cảnh báo trước khi
chỉnh sửa. Việc sửa brief không tự xóa, ghi đè hoặc thay đổi file TXT/output.

## 5. Đặc tả API

Các endpoint dưới đây có tiền tố `/api`. FastAPI tự sinh tài liệu tại
`http://127.0.0.1:8000/docs` khi backend đang chạy.

| Phương thức | Endpoint | Mô tả |
|---|---|---|
| GET | `/api/health` | Kiểm tra backend |
| GET | `/api/overview?date=YYYY-MM-DD` | Lấy thẻ và thống kê của ngày; prompt được lấy riêng sau khi template đã cấu hình |
| POST | `/api/days` | Tạo ngày và phân bổ 42 brief |
| GET | `/api/history` | Lấy lịch sử các ngày |
| GET | `/api/days/{date}/items/{uid}/prompt?mode=...` | Sinh prompt `full`, `part1` hoặc `part2` |
| GET | `/api/prompt-templates` | Lấy ba template và danh sách biến hợp lệ |
| PUT | `/api/prompt-templates/{mode}` | Lưu một template |
| DELETE | `/api/prompt-templates/{mode}` | Xóa một template |
| POST | `/api/prompt-templates/preview` | Xem trước template sau khi thay biến |
| POST | `/api/days/{date}/items/{uid}/copied` | Ghi nhận sao chép thành công |
| POST | `/api/days/{date}/items/{uid}/undo-copied` | Hoàn tác sao chép, đưa về `ready` |
| POST | `/api/days/{date}/items/{uid}/toggle-done` | Đổi qua lại giữa `done` và `sent` |
| PATCH | `/api/days/{date}/items/{uid}/brief` | Cập nhật 7 trường nội dung |
| GET | `/api/days/{date}/scan` | Rà trùng toàn bộ ngày |
| POST | `/api/days/{date}/items/{uid}/scan` | Rà trùng một brief, kể cả nội dung đang sửa |
| GET | `/api/planning-prompt?date=...&ai=...` | Lấy prompt lập kế hoạch 14 brief |
| POST | `/api/days/{date}/plan` | Nhập một batch 14 brief |
| GET | `/api/backup` | Tải JSON schema v2 |
| POST | `/api/restore` | Kiểm tra và thay thế dữ liệu bằng JSON schema v2 |
| POST | `/api/workspace/export` | Xuất 14 prompt Full thành TXT cho một lane |
| GET | `/api/workspace/config` | Xem workspace và quyền đọc/ghi |
| PUT | `/api/workspace/config` | Xác nhận workspace tuyệt đối mới |
| GET | `/api/workspace/status?date=...&ai=...` | Kiểm tra prompt/output theo 14 slot |
| GET | `/api/workspace/file?date=...&ai=...&slot=...&kind=...` | Đọc prompt hoặc output |
| PUT | `/api/workspace/file` | Sửa và lưu prompt/output có kiểm tra hash |
| DELETE | `/api/workspace/file?date=...&ai=...&slot=...&kind=...` | Xóa prompt/output |

Ngày phải có định dạng `YYYY-MM-DD` hợp lệ. API dùng mã lỗi `422` cho dữ liệu
không hợp lệ, `404` khi không tìm thấy ngày hoặc thẻ, `409` cho xung đột
trạng thái hoặc thao tác ghi đè bị chặn.

## 6. Bảo mật và giới hạn

- Ứng dụng không có xác thực, phân quyền người dùng hoặc quản lý tài khoản.
- Chỉ chạy nội bộ; không được đưa trực tiếp instance chưa xác thực lên
  Internet.
- Nếu triển khai công khai phải bổ sung xác thực, phân quyền, HTTPS, CSRF
  protection phù hợp, logging, giám sát và chính sách sao lưu.
- Clipboard có thể bị trình duyệt chặn nếu không chạy trên `localhost` hoặc
  HTTPS.
- Không có đồng bộ thời gian thực giữa nhiều trình duyệt; các ghi SQLite được
  tuần tự hóa nhưng giao diện phải tải lại dữ liệu để thấy thay đổi từ client
  khác.
- Ứng dụng không lưu toàn văn truyện hoàn chỉnh.
- Prompt và output TXT được lưu ngoài SQLite trong workspace cục bộ; workspace
  phải được đưa ra ngoài GitHub và không được commit vào repository.
- Backend không tự động gọi Gemini hoặc kiểm tra độ dài truyện; Extension
  tiếp tục là thành phần đọc prompt và tạo output.
- Chất lượng, độ dài và giới hạn trả lời của dịch vụ AI bên ngoài không thuộc
  phạm vi kiểm soát của THẮNG MIA.

## 7. Tiêu chí nghiệm thu

1. Tạo hai ngày liên tiếp không tái sử dụng starter brief.
2. Mỗi ngày có 42 thẻ, gồm 14 thẻ cho mỗi AI và 3 thẻ mỗi nhóm chủ đề.
3. Ba template mới mặc định trống và không nạp prompt cũ.
4. Sao chép thành công cập nhật trạng thái; sao chép thất bại không cập nhật.
5. Nhấn **Sao chép tiếp** không reload trang và cập nhật đúng bộ đếm.
6. **Hoàn tác sao chép** chuyển `sent`/`part1` về `ready`, giảm thống kê và
   không reload trang.
7. Không thể hoàn tác sao chép trực tiếp khi thẻ đang `done`.
8. Chỉnh sửa brief làm thay đổi prompt sinh ra và dữ liệu vẫn còn sau khi khởi
   động lại backend.
9. Nhập batch thiếu dòng, lane đã giao hoặc dữ liệu sai định dạng bị từ chối.
10. Cảnh báo trùng từ khóa yêu cầu xác nhận trước khi nhập.
11. Sao lưu/khôi phục giữ nguyên ngày, brief và trạng thái.
12. Xuất prompt tạo đủ 14 file đúng lane, đúng slot và không ghi đè file đã có.
13. Web đọc đúng output theo manifest; output thiếu hiển thị **Chưa có kết quả**.
14. Sửa/xóa TXT không thay đổi brief hoặc trạng thái trong SQLite.
15. Workspace tương đối, symbolic link hoặc file không có mapping hợp lệ bị từ chối.
16. `npm run lint`, `npm run typecheck`, `npm run build` và bộ test API backend
    chạy thành công.

## 8. Ngoài phạm vi phiên bản 3.2.0

- Tài khoản người dùng và phân quyền.
- Hosting công khai và đồng bộ realtime.
- Tích hợp trực tiếp với API hoặc website AI.
- Tự động đăng Facebook.
- Phân tích ngữ nghĩa hoặc kiểm tra đạo văn.
- Nhập, lưu trữ hoặc xử lý truyện hoàn chỉnh.
- Sửa đổi hoặc triển khai Chrome Extension.
