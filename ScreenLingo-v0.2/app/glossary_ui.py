"""Editable, local-only proper-name and loanword preferences."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
    QTableWidget,QTableWidgetItem,QHeaderView,QDialogButtonBox,QMessageBox)
from core import normalize


class GlossaryDialog(QDialog):
    def __init__(self,entries,parent=None):
        super().__init__(parent)
        self.setWindowTitle('이름·외래어 사전')
        self.resize(600,460)
        layout=QVBoxLayout(self)
        help_text=QLabel('원문과 원하는 한국어 표기를 등록하세요. 인명·캐릭터명·지명·외래어에 적용됩니다.\n'
                        '예: カタリナ → 카타리나. 한자 이름도 등록할 수 있습니다.\n'
                        '원문은 OCR이 읽은 글자와 일치해야 합니다. 전체 번역 보기에서 확인하세요.')
        help_text.setWordWrap(True); layout.addWidget(help_text)
        self.table=QTableWidget(0,2)
        self.table.setHorizontalHeaderLabels(['원문','원하는 한국어 표기'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.table)
        for original,target in entries.items(): self.add_row(original,target)
        if not entries: self.add_row()
        actions=QHBoxLayout()
        add=QPushButton('단어 추가'); add.clicked.connect(lambda:self.add_row()); actions.addWidget(add)
        remove=QPushButton('선택 삭제'); remove.clicked.connect(self.remove_rows); actions.addWidget(remove)
        layout.addLayout(actions)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText('저장')
        buttons.button(QDialogButtonBox.Cancel).setText('취소')
        buttons.accepted.connect(self.validate_and_accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_row(self,original='',target=''):
        row=self.table.rowCount(); self.table.insertRow(row)
        self.table.setItem(row,0,QTableWidgetItem(original))
        self.table.setItem(row,1,QTableWidgetItem(target))

    def remove_rows(self):
        for row in sorted({index.row() for index in self.table.selectedIndexes()},reverse=True):
            self.table.removeRow(row)

    def entries(self):
        result={}
        for row in range(self.table.rowCount()):
            source=normalize(self.table.item(row,0).text())
            target=normalize(self.table.item(row,1).text())
            if not source and not target: continue
            if not source or not target: raise ValueError(f'{row+1}행의 원문과 한국어 표기를 모두 입력하세요.')
            if source in result: raise ValueError(f'원문이 중복되었습니다: {source}')
            result[source]=target
        return result

    def validate_and_accept(self):
        try: self.entries()
        except ValueError as exc:
            QMessageBox.warning(self,'사전 확인',str(exc)); return
        self.accept()
