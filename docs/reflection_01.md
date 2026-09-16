# Reflection 01

## 1. Khó khăn khi cài Docker/DBeaver và cách bạn xử lý?

Mình xử lý bằng cách sử dụng Claude CLI. Tuy nhiên, mình cần phải có khả năng điều khiển nó, không để nó sửa các file trong hệ thống một cách lung tung.

## 2. Vì sao chọn data type như vậy cho tiền tệ / thời gian / ID? Cho 1 ví dụ cụ thể.

Với tiền tôi dùng kiểu số thập phân. Lý do thứ nhất, nó chính xác về mặt tiền tệ, không làm tròn như kiểu float, tránh rủi ro bị sai khác dữ liệu khi tính tổng. Tương tự, khi tính giảm giá, tính thanh toán cũng thế.

Với thời gian tôi dùng kiểu thời gian cộng với múi giờ. Lợi ích đó là có thể lọc dữ liệu theo ngày, có tác dụng trong việc trích xuất dữ liệu nhanh chóng. Hơn nữa, mình có thể tính khoảng thời gian dựa trên danh sách các timestamp. Thêm nữa, mình có thể xác định dữ liệu cũ hoặc mới dựa trên danh sách dữ liệu được sắp xếp theo thời gian. Tạo báo cáo theo thời gian cũng là một lợi ích không thể bỏ qua.

Với ID thì lưu cả số và chữ. Thay vì lưu ID bằng tự động tăng của database thì mình sẽ gán cho nó một định danh dễ quản lý. Việc định danh ID bằng cus011, odr011,.. giúp dễ dàng phân biệt và quản lý hơn so với dùng số 1, 2, 4,…

## 3. Hiểu thế nào về quan hệ 1:N giữa customers và orders? Vẽ/kể ví dụ 1 customer có N orders.

Mối quan hệ này nghĩa là khách hàng có thể có nhiều đơn hàng và ngược lại, một đơn hàng chỉ thuộc một khách hàng. Ví dụ, khách hàng mua laptop thì hệ thống sẽ tạo cho khách hàng đó một order. Tuy nhiên, khách hàng đó có thể mua thêm iphone nữa, hệ thống lại tạo cho khách hàng đó một order khác. Vậy khách hàng có thể sở hữu nhiều order. Hơn nữa, đơn hàng của khách hàng nào chỉ thuộc khách hàng đó thôi, nên không có chuyện khách hàng A có order giống với khách hàng B, dù họ cùng mua chung một sản phẩm, vì đơn hàng có thông tin khác với thông tin của sản phẩm.

## 4. Nếu schema cần sửa sau này (thêm cột, đổi FK), bạn sẽ xử lý thế nào (ALTER vs tạo lại)?

Theo mình là sử dụng ALTER vì nếu tạo lại có thể mất dữ liệu đã được seed nếu có.
