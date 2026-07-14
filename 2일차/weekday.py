import calendar  # 달력 데이터 생성용 표준 라이브러리
import os
import sys

# 요일 헤더 (월요일부터 시작)
WEEKDAY_HEADERS = ["월", "화", "수", "목", "금", "토", "일"]

# 터미널 ANSI 색상 코드 (토: 파란색, 일: 빨간색)
BLUE = "\033[34m"
RED = "\033[31m"
RESET = "\033[0m"  # 색상 초기화


def enable_ansi_colors():
    """Windows 터미널에서 ANSI 색상 출력을 활성화한다."""
    if sys.platform == "win32":
        os.system("")


def colorize(text, col_index):
    """열 인덱스에 따라 토요일(5)은 파란색, 일요일(6)은 빨간색으로 칠한다."""
    if col_index == 5:
        return f"{BLUE}{text}{RESET}"
    if col_index == 6:
        return f"{RED}{text}{RESET}"
    return text


def print_calendar(year, month):
    """입력받은 년·월의 달력을 요일과 함께 출력한다."""
    print(f"\n     {year}년 {month}월")

    # 요일 헤더 출력
    print(
        " ".join(
            colorize(f"{day:>3}", i) for i, day in enumerate(WEEKDAY_HEADERS)
        )
    )

    # monthcalendar: 각 주를 [월, 화, ..., 일] 리스트로 반환 (빈 칸은 0)
    for week in calendar.monthcalendar(year, month):
        row = []
        for col_index, day in enumerate(week):
            if day == 0:
                row.append("   ")  # 해당 월에 속하지 않는 날짜
            else:
                row.append(colorize(f"{day:3d}", col_index))
        print(" ".join(row))


def main():
    enable_ansi_colors()
    year = int(input("년(year)을 입력하세요: "))
    month = int(input("월(month, 1~12)을 입력하세요: "))
    
    print_calendar(year, month)


if __name__ == "__main__":
    main()
