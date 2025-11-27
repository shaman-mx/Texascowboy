/* Validate selections before submitting the save form */
function getSelectedBoxes() {
  // nếu bạn dùng input checkbox: uncomment và dùng querySelectorAll('input[name="selected_box"]:checked')
  // return Array.from(document.querySelectorAll('input[name="selected_box"]:checked')).map(i=>i.value);

  // nếu bạn dùng div click-to-toggle (data-val) như template hiện tại:
  return Array.from(document.querySelectorAll('.box.selected')).map(el => el.getAttribute('data-val'));
}

function validateAndSubmit() {
  const TOP = ["cowboy_win","draw","bull_win"];
  const RIGHT = ["high_onepair","two_pair","trips","full_house","four_kind"];

  const selected = getSelectedBoxes();
  const topSel = selected.filter(s => TOP.includes(s));
  const rightSel = selected.filter(s => RIGHT.includes(s));
  const rightsExclFk = rightSel.filter(s => s !== "four_kind");

  if (topSel.length === 0) {
    alert("Lỗi: phải chọn 1 ô trong TOP (cowboy_win, draw, bull_win).");
    return;
  }
  if (topSel.length > 1) {
    alert("Lỗi: chỉ được chọn đúng 1 ô trong TOP.");
    return;
  }
  if (rightSel.length === 0) {
    alert("Lỗi: phải chọn ít nhất 1 ô trong RIGHT (high_onepair, two_pair, trips, full_house, four_kind).");
    return;
  }
  if (rightsExclFk.length > 1) {
    alert("Lỗi: chỉ được chọn tối đa 1 ô trong RIGHT (không tính tứ quý).");
    return;
  }

  // map selections vào form (ẩn) trước submit
  const container = document.getElementById("selected-container");
  container.innerHTML = ""; // clear previous
  selected.forEach(k => {
    const inp = document.createElement("input");
    inp.type = "hidden";
    inp.name = "selected_box";
    inp.value = k;
    container.appendChild(inp);
  });

  // ensure first_card hidden input is set (already present in template)
  document.getElementById("save-first-card").value = document.getElementById("save-first-card").value || "";

  document.getElementById("save-form").submit();
}

/* Optional: wire Enter key or form submit to validation */
document.addEventListener("DOMContentLoaded", function(){
  const form = document.getElementById("save-form");
  if (form) {
    form.addEventListener("submit", function(e){
      e.preventDefault();
      validateAndSubmit();
    });
  }
});