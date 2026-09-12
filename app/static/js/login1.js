document.addEventListener("DOMContentLoaded", function () {
  //   form tag중 action 속성의 값이 "/login" 인것을 찾아라
  const loginForm = document.querySelector('form[action="/login"]');

  loginForm.addEventListener("submit", function (event) {
    // 여기에 유효성 검사나 추가 처리 로직 작성 가능
    // 예: username, password 빈 값 체크 등
    const username = loginForm.username.value.trim();
    const password = loginForm.password.value.trim();

    if (!username || !password) {
      event.preventDefault();
      alert("Please enter both username and password.");
    }
  });
});
