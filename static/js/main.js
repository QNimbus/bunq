// Description: Main JavaScript file for the application

const main = (() => {
  document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById("detailModal");
    const modalText = document.getElementById("modal-text");
    const loginForm = document.getElementById("login");
    const tableRows = document.querySelectorAll("tr.main-row, tr.detail-row");
    const rootStyle = getComputedStyle(document.documentElement);
    const transitionDuration = rootStyle.getPropertyValue(
      "--modal-transition-duration"
    );
    const durationInMs = parseFloat(transitionDuration) * 1000; // Convert the duration from seconds to milliseconds for setTimeout

    /* Utility functions */

    function isValidBase64(str) {
      const base64Regex =
        /^(?:[A-Za-z0-9+\/]{4})*(?:[A-Za-z0-9+\/]{2}==|[A-Za-z0-9+\/]{3}=)?$/;
      return base64Regex.test(str);
    }

    function decodeBase64() {
      document.querySelectorAll("span.encodedData").forEach((elem) => {
        if (elem.children.length === 0 && isValidBase64(elem.textContent)) {
          elem.textContent = atob(elem.textContent).slice(0, 100);
          elem.classList.add("ellipsis");
        }
      });
    }

    /* DOM functions */

    function toggleDetailRow(clickedRow) {
      const detailRow = clickedRow.nextElementSibling;
      const chevron = clickedRow.querySelector(".rotating-chevron");

      if (!detailRow || !detailRow.classList.contains("detail-row")) {
        return; // Exit if there's no detail row or if it's not the correct class
      }

      // Toggle the current row and chevron
      detailRow.classList.toggle("visible");
      if (chevron) {
        chevron.classList.toggle("rotate-chevron");
      }

      // Iterate through siblings to close other rows and rotate their chevrons back
      let sibling = clickedRow.parentNode.firstElementChild;
      while (sibling) {
        if (sibling !== clickedRow && sibling.classList.contains("main-row")) {
          const siblingChevron = sibling.querySelector(".rotating-chevron");
          const siblingDetailRow = sibling.nextElementSibling;

          if (
            siblingChevron &&
            siblingChevron.classList.contains("rotate-chevron")
          ) {
            siblingChevron.classList.remove("rotate-chevron");
          }

          if (
            siblingDetailRow &&
            ["visible", "detail-row"].every((className) =>
              siblingDetailRow.classList.contains(className)
            )
          ) {
            siblingDetailRow.classList.remove("visible");
          }
        }
        sibling = sibling.nextElementSibling;
      }
    }

    function showModal(event) {
      const clickedElement = event.target;
      const modalTitle = clickedElement.getAttribute("data-modal-title");
      const decodedData = JSON.parse(
        atob(clickedElement.getAttribute("data-modal-content"))
      );
      let content = `<strong>${modalTitle}:</strong><br>`;

      Object.entries(decodedData).forEach(([key, value]) => {
        let displayData =
          typeof value === "object"
            ? JSON.stringify(value, null, 2)
                .replace(/^( +)/gm, (match) => match.replace(/ /g, "&nbsp;"))
                .replace(/\n/g, "<br>")
            : value;
        content += `${key}: ${displayData}<br>`;
      });

      modalText.innerHTML = content;
      modal.style.display = "block";
      setTimeout(
        () => modal.querySelector(".modal-content").classList.add("show"),
        0
      ); // Wait for the next tick to add the class
    }

    function closeModal() {
      modal.querySelector(".modal-content").classList.remove("show");
      setTimeout(() => (modal.style.display = "none"), durationInMs);
    }

    /* Event handlers */

    async function submitLoginForm(event) {
      event.preventDefault(); // Prevent the default form submission

      const formData = new FormData(loginForm);
      const formObject = Object.fromEntries(formData.entries());

      try {
        const response = await fetch("/login", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(formObject),
        });

        if (response.redirected) {
          window.location.href = response.url;
        } else if (!response.ok) {
          // Handle the response here (e.g., redirecting the user or displaying a message)
        }
      } catch (error) {
        console.error("Error during form submission:", error);
        // Handle the error (e.g., displaying an error message to the user)
      }
    }

    /* Event listeners */

    // Global 'click' event listener
    document.addEventListener("click", (event) => {
      const clickedElement = event.target;
      const mainRow = clickedElement.closest(".main-row");

      if (clickedElement.hasAttribute("data-modal-title")) {
        showModal(event);
      } else if (
        clickedElement.classList.contains("close") ||
        clickedElement === modal
      ) {
        closeModal();
      } else if (
        mainRow &&
        mainRow.tagName === "TR" &&
        clickedElement.tagName !== "INPUT" &&
        clickedElement.tagName !== "BUTTON"
      ) {
        toggleDetailRow(mainRow);
      }
    });

    if (loginForm) {
      loginForm.addEventListener("submit", submitLoginForm);
    }

    if (tableRows) {
      tableRows.forEach((row) => {
        row.addEventListener("mouseover", function () {
          const previousSibling = row.previousElementSibling;
          const nextSibling = row.nextElementSibling;

          if (
            row.classList.contains("main-row") &&
            nextSibling?.classList.contains("detail-row")
          ) {
            row.classList.add("highlight");
            nextSibling.classList.add("highlight");
          } else if (
            row.classList.contains("detail-row") &&
            previousSibling?.classList.contains("main-row")
          ) {
            row.classList.add("highlight");
            previousSibling.classList.add("highlight");
          }
        });

        row.addEventListener("mouseout", function () {
          const previousSibling = row.previousElementSibling;
          const nextSibling = row.nextElementSibling;

          if (
            row.classList.contains("main-row") &&
            nextSibling?.classList.contains("detail-row")
          ) {
            row.classList.remove("highlight");
            nextSibling.classList.remove("highlight");
          } else if (
            row.classList.contains("detail-row") &&
            previousSibling?.classList.contains("main-row")
          ) {
            row.classList.remove("highlight");
            previousSibling.classList.remove("highlight");
          }
        });
      });
    }

    // Decode base64 data on page load
    decodeBase64();
  });
})();
