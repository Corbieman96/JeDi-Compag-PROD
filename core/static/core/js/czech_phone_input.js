(function () {
    function digitsOnly(s) {
        return String(s || "").replace(/\D/g, "");
    }

    function formatNational9(digits) {
        const d = digits.slice(0, 9);
        if (d.length <= 3) return d;
        if (d.length <= 6) return d.slice(0, 3) + " " + d.slice(3);
        return d.slice(0, 3) + " " + d.slice(3, 6) + " " + d.slice(6);
    }

    function format(value) {
        let dig = digitsOnly(value);
        if (!dig) return "";
        if (dig.length > 9) dig = dig.slice(-9);
        return formatNational9(dig);
    }

    function digitCountBefore(str, pos) {
        let n = 0;
        const end = Math.min(pos == null ? str.length : pos, str.length);
        for (let i = 0; i < end; i++) {
            if (/\d/.test(str[i])) n++;
        }
        return n;
    }

    function positionAfterNthDigit(formatted, n) {
        if (n <= 0) return 0;
        let seen = 0;
        for (let i = 0; i < formatted.length; i++) {
            if (/\d/.test(formatted[i])) {
                seen++;
                if (seen === n) return i + 1;
            }
        }
        return formatted.length;
    }

    function bind(input) {
        if (!input) return;

        function sync() {
            const cur = input.selectionStart == null ? input.value.length : input.selectionStart;
            const before = digitCountBefore(input.value, cur);
            const next = format(input.value);
            input.value = next;
            const pos = Math.min(positionAfterNthDigit(next, before), next.length);
            try {
                input.setSelectionRange(pos, pos);
            } catch (e) {}
        }

        input.addEventListener("input", sync);
        input.addEventListener("blur", sync);
        sync();
    }

    window.CzechPhoneInput = { format, bind };
})();
