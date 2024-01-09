// Description: Main JavaScript file for the application

import { Utils, ajax } from "./ajax.js";

const main = (() => {
  document.addEventListener("DOMContentLoaded", () => {
    /* Modal variables */
    const modal = document.getElementById("detailModal");
    const modalText = document.getElementById("modal-text");
    const rootStyle = getComputedStyle(document.documentElement);
    const transitionDuration = rootStyle.getPropertyValue(
      "--modal-transition-duration"
    );
    const durationInMs = parseFloat(transitionDuration) * 1000; // Convert the duration from seconds to milliseconds for setTimeout

    /* Login form variables */
    const loginForm = document.getElementById("login-form");

    /* NavBar variables */
    const lougoutButton = document.getElementById("logout-button");
    const requestsTable = document.getElementById("table-requests");

    /* Table variables */
    const selectAllCheckbox = document.getElementById("select-all");
    const removeAllButton = document.getElementById("remove-all");

    /* DOM helper functions */

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

    function toggleRowHighlight(targetElement, highlight) {
      const row = targetElement.closest("tr");
      if (!row) return;

      const previousSibling = row.previousElementSibling;
      const nextSibling = row.nextElementSibling;

      if (
        (row.classList.contains("main-row") &&
          nextSibling?.classList.contains("detail-row")) ||
        (row.classList.contains("detail-row") &&
          previousSibling?.classList.contains("main-row"))
      ) {
        row.classList.toggle("highlight", highlight);
        (row.classList.contains("main-row")
          ? nextSibling
          : previousSibling
        ).classList.toggle("highlight", highlight);
      }
    }

    function handleTableRowClick(clickedElement) {
      const mainRow = clickedElement.closest(".main-row");
      if (
        mainRow &&
        mainRow.tagName === "TR" &&
        !["INPUT", "BUTTON"].includes(clickedElement.tagName)
      ) {
        toggleDetailRow(mainRow);
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

    // Load the first page of requests, if the table exists
    if (requestsTable) {
      ajax.loadPage();
    }

    // Login form submission
    if (loginForm) {
      loginForm.addEventListener("submit", submitLoginForm);
    }

    // Logout button click
    if (lougoutButton) {
      lougoutButton.addEventListener("click", () => {
        fetch("/logout", { method: "DELETE" })
          .then((response) => {
            if (response.redirected) {
              window.location.href = response.url;
            } else if (!response.ok) {
              // Handle the response here (e.g., redirecting the user or displaying a message)
            }
          })
          .catch((error) => {
            console.error("Error during logout:", error);
            // Handle the error (e.g., displaying an error message to the user)
          });
      });
    }

    // Select all checkbox click
    if (selectAllCheckbox) {
      selectAllCheckbox.addEventListener("change", (event) => {
        const rowCheckboxes = document.querySelectorAll(".row-checkbox");
        rowCheckboxes.forEach((checkbox) => {
          checkbox.checked = event.target.checked;
        });
      });
    }

    document.addEventListener("change", (event) => {
      // Return early if change event is not from a checkbox
      if (event.target.type !== "checkbox") return;

      /* If any of the .row-checkbox elements are checked, enable the delete button */
      const checkedCheckboxes = document.querySelectorAll(
        ".row-checkbox:checked"
      );

      if (checkedCheckboxes.length > 0) {
        removeAllButton.classList.remove("disabled");
      } else {
        removeAllButton.classList.add("disabled");
      }
    });

    // Global click event listener
    document.addEventListener("click", (event) => {
      const clickedElement = event.target;

      if (
        clickedElement.hasAttribute("data-action") &&
        clickedElement.getAttribute("data-action") === "delete"
      ) {
        const requestUuid = clickedElement.getAttribute("data-request-uuid");

        ajax.deleteRequest(requestUuid);
      } else if (clickedElement.hasAttribute("data-modal-title")) {
        showModal(event);
      } else if (
        clickedElement.classList.contains("close") ||
        clickedElement === modal
      ) {
        closeModal();
      } else if (clickedElement.classList.contains("rotating-chevron")) {
        handleTableRowClick(clickedElement);
      }
    });

    // Global mouseover and mouseout event listeners
    document.addEventListener("mouseover", (event) => {
      toggleRowHighlight(event.target, true);
    });

    // Global mouseover and mouseout event listeners
    document.addEventListener("mouseout", (event) => {
      toggleRowHighlight(event.target, false);
    });
  });
})();
